import { expect, test } from "@playwright/test"

import { createAuthorizedApiContext, loginByUi, prepareOnShelfArchive } from "./support"

interface ApiResponseShape<T> {
  data: T
  message: string
  code: number
}

async function createBorrowApplicationByApi(archiveId: number) {
  const apiContext = await createAuthorizedApiContext("borrower", "Borrower12345")

  try {
    const response = await apiContext.post("borrowing/applications/", {
      data: {
        archive_id: archiveId,
        purpose: "E2E 借阅闭环联调测试",
        expected_return_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
      },
    })
    expect(response.ok()).toBeTruthy()
    const payload = await response.json() as ApiResponseShape<{ id: number }>
    return payload.data.id
  } finally {
    await apiContext.dispose()
  }
}

test("借阅申请应能完成审批、出库、归还与通知回跳闭环", async ({ browser }) => {
  const archive = await prepareOnShelfArchive({
    codePrefix: "E2E-BORROW",
    titlePrefix: "E2E 借阅闭环档案",
    summary: "用于借阅、审批、出库、归还闭环的联调验证。",
  })
  const applicationId = await createBorrowApplicationByApi(archive.archiveId)

  const borrowerContext = await browser.newContext()
  const adminContext = await browser.newContext()
  const borrowerPage = await borrowerContext.newPage()
  const adminPage = await adminContext.newPage()

  try {
    await loginByUi(borrowerPage, "borrower", "Borrower12345")
    await borrowerPage.goto(`/borrowing/applications?applicationId=${applicationId}`)
    await expect(borrowerPage).toHaveURL(/\/borrowing\/applications\?applicationId=/)
    await expect(borrowerPage.getByText("借阅申请详情")).toBeVisible()
    const applicationDetailDrawer = borrowerPage.locator(".ant-drawer")
    await expect(applicationDetailDrawer.getByText(archive.archiveCode, { exact: true })).toBeVisible()
    await expect(applicationDetailDrawer.getByText("待审批", { exact: true }).first()).toBeVisible()

    const borrowerApplicationRow = borrowerPage.locator(".ant-table-tbody tr").filter({ hasText: archive.archiveCode })
    await expect(borrowerApplicationRow).toBeVisible()
    await expect(borrowerApplicationRow).toContainText("待审批")

    await loginByUi(adminPage, "admin", "Admin12345")
    await adminPage.goto("/borrowing/approvals")
    await expect(adminPage).toHaveURL(/\/borrowing\/approvals$/)
    await adminPage.getByPlaceholder("按申请编号、档号、题名或申请人搜索").fill(archive.archiveCode)
    await adminPage.getByRole("button", { name: "刷新审批列表" }).click()

    const approvalRow = adminPage.locator(".ant-table-tbody tr").filter({ hasText: archive.archiveCode })
    await expect(approvalRow).toBeVisible()
    await approvalRow.getByRole("button", { name: "审批通过" }).click()
    await adminPage.getByPlaceholder("可补充审批说明").fill("E2E 审批通过")
    await adminPage.getByRole("button", { name: "确认通过" }).click()
    await expect(approvalRow).toHaveCount(0)

    await adminPage.goto("/borrowing/checkout")
    await adminPage.getByPlaceholder("按申请编号、档号、题名或申请人搜索").fill(archive.archiveCode)
    await adminPage.getByRole("button", { name: "刷新待出库列表" }).click()

    const checkoutRow = adminPage.locator(".ant-table-tbody tr").filter({ hasText: archive.archiveCode })
    await expect(checkoutRow).toBeVisible()
    await checkoutRow.getByRole("button", { name: "办理出库" }).click()
    await adminPage.getByPlaceholder("可填写线下签收情况、交接说明或其他备注").fill("E2E 办理出库")
    await adminPage.getByRole("button", { name: "确认出库" }).click()
    await expect(checkoutRow).toHaveCount(0)

    await borrowerPage.goto("/borrowing/returns")
    await expect(borrowerPage).toHaveURL(/\/borrowing\/returns$/)

    const returnTaskRow = borrowerPage.locator(".ant-table-tbody tr").filter({ hasText: archive.archiveCode })
    await expect(returnTaskRow).toBeVisible()
    await returnTaskRow.getByRole("button", { name: "提交归还" }).click()
    await borrowerPage.getByPlaceholder("补充说明交接情况、附件内容或异常说明").fill("E2E 提交归还")

    const uploadInputs = borrowerPage.locator('input[type="file"]')
    await uploadInputs.nth(0).setInputFiles({
      name: "borrow-return-photo.jpg",
      mimeType: "image/jpeg",
      buffer: Buffer.from("e2e-borrow-return-photo"),
    })

    await borrowerPage.getByRole("button", { name: "确认提交" }).click()

    await adminPage.goto("/borrowing/returns")
    await expect(adminPage).toHaveURL(/\/borrowing\/returns$/)

    const confirmPanel = adminPage.locator(".panel-card").filter({ hasText: "归还确认待办" }).first()
    const confirmRow = confirmPanel.locator(".ant-table-tbody tr").filter({ hasText: archive.archiveCode })
    await expect(confirmRow).toBeVisible()
    await confirmRow.getByRole("button", { name: "处理确认" }).click()
    await adminPage.getByPlaceholder("可填写重新入库说明").fill("E2E 验收通过并重新入库")
    await adminPage.getByRole("button", { name: "提交确认" }).click()
    await expect(confirmRow).toHaveCount(0)

    await borrowerPage.goto("/notifications/messages")
    await expect(borrowerPage).toHaveURL(/\/notifications\/messages$/)

    const notificationRow = borrowerPage.locator(".ant-table-tbody tr").filter({ hasText: "档案归还已确认入库" }).first()
    await expect(notificationRow).toBeVisible()
    await notificationRow.getByRole("button", { name: "查看业务" }).click()

    await expect(borrowerPage).toHaveURL(/\/borrowing\/applications\?applicationId=/)
    await expect(borrowerPage.getByText("借阅申请详情")).toBeVisible()
    const returnedDetailDrawer = borrowerPage.locator(".ant-drawer")
    await expect(returnedDetailDrawer.getByText(archive.archiveCode, { exact: true })).toBeVisible()
    await expect(returnedDetailDrawer.getByText("已归还", { exact: true }).first()).toBeVisible()
    await expect(returnedDetailDrawer.getByText("已确认入库", { exact: true }).first()).toBeVisible()
  } finally {
    await borrowerContext.close()
    await adminContext.close()
  }
})
