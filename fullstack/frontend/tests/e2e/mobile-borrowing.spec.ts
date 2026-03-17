import { expect, test } from "@playwright/test"

import { createAuthorizedApiContext, loginByUi, prepareOnShelfArchive } from "./support"

interface ApiResponseShape<T> {
  data: T
  message: string
  code: number
}

test.use({
  viewport: {
    width: 390,
    height: 844,
  },
})

async function createBorrowApplicationByApi(archiveId: number) {
  const apiContext = await createAuthorizedApiContext("borrower", "Borrower12345")

  try {
    const response = await apiContext.post("borrowing/applications/", {
      data: {
        archive_id: archiveId,
        purpose: "移动端借阅流程联调测试",
        expected_return_at: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString(),
      },
    })
    expect(response.ok()).toBeTruthy()
    const payload = await response.json() as ApiResponseShape<{ id: number }>
    return payload.data.id
  } finally {
    await apiContext.dispose()
  }
}

test("借阅人在移动端断点下应能查看借阅列表、创建表单和申请详情", async ({ page }) => {
  test.setTimeout(90_000)

  const archive = await prepareOnShelfArchive({
    codePrefix: "E2E-MOBILE-BORROW",
    titlePrefix: "移动端借阅联调档案",
    summary: "用于移动端借阅页面联调验证。",
  })
  const applicationId = await createBorrowApplicationByApi(archive.archiveId)

  await loginByUi(page, "borrower", "Borrower12345")
  await page.goto(`/borrowing/applications?applicationId=${applicationId}`)

  await expect(page).toHaveURL(/\/borrowing\/applications\?applicationId=/)
  await expect(page.getByText("新建借阅申请", { exact: true })).toBeVisible()
  await expect(page.getByLabel("档案选择")).toBeVisible()
  await expect(page.getByRole("button", { name: "提交申请" })).toBeVisible()

  const applicationDetailDrawer = page.locator(".ant-drawer")
  await expect(applicationDetailDrawer.getByText("借阅申请详情", { exact: true })).toBeVisible()
  await expect(applicationDetailDrawer.getByText(archive.archiveCode, { exact: true })).toBeVisible()
  await expect(applicationDetailDrawer.getByText("待审批", { exact: true }).first()).toBeVisible()

  const listRow = page.locator(".ant-table-tbody tr").filter({ hasText: archive.archiveCode }).first()
  await expect(listRow).toBeVisible()
  await expect(listRow).toContainText("待审批")
})
