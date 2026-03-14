import { expect, test } from "@playwright/test"

import { loginByUi, prepareOnShelfArchive } from "./support"

test("销毁申请应能完成申请、审批、执行与通知回跳闭环", async ({ browser }) => {
  const archive = await prepareOnShelfArchive({
    codePrefix: "E2E-DESTROY",
    titlePrefix: "E2E 销毁闭环档案",
    summary: "用于销毁申请、审批、执行与通知回跳闭环的联调验证。",
  })

  const archivistContext = await browser.newContext()
  const adminContext = await browser.newContext()
  const archivistPage = await archivistContext.newPage()
  const adminPage = await adminContext.newPage()

  try {
    await loginByUi(archivistPage, "archivist", "Archivist12345")
    await archivistPage.goto("/destruction/applications")
    await expect(archivistPage).toHaveURL(/\/destruction\/applications$/)

    await archivistPage.getByRole("button", { name: "发起销毁申请" }).click()
    const createModal = archivistPage.locator(".ant-modal-content").filter({ hasText: "发起销毁申请" }).first()
    await expect(createModal).toBeVisible()
    await createModal.locator(".ant-select-selector").click()

    const archiveOption = archivistPage
      .locator(".ant-select-dropdown:visible .ant-select-item-option")
      .filter({ hasText: archive.archiveCode })
      .first()
    await expect(archiveOption).toBeVisible()
    await archiveOption.click()

    await createModal.getByPlaceholder("例如：保管期限届满且无继续保存价值").fill("E2E 销毁执行闭环申请原因")
    await createModal.getByPlaceholder("请填写制度条款、审签依据或业务规定").fill("E2E 销毁制度依据")
    await createModal.getByRole("button", { name: "提交申请" }).click()

    const pendingRow = archivistPage.locator(".ant-table-tbody tr").filter({ hasText: archive.archiveCode })
    await expect(pendingRow).toBeVisible()
    await expect(pendingRow).toContainText("待审批")
    await pendingRow.getByRole("button", { name: "查看详情" }).click()

    await expect(archivistPage.getByText("销毁申请详情")).toBeVisible()
    const pendingDetailDrawer = archivistPage.locator(".ant-drawer")
    await expect(pendingDetailDrawer.getByText(archive.archiveCode, { exact: true })).toBeVisible()
    await expect(pendingDetailDrawer.getByText("待审批", { exact: true }).first()).toBeVisible()

    await loginByUi(adminPage, "admin", "Admin12345")
    await adminPage.goto("/destruction/applications")
    await expect(adminPage).toHaveURL(/\/destruction\/applications$/)
    await adminPage.getByPlaceholder("按申请编号、档号、题名或申请人搜索").fill(archive.archiveCode)
    await adminPage.getByRole("button", { name: "刷新列表" }).click()

    const approvalRow = adminPage.locator(".ant-table-tbody tr").filter({ hasText: archive.archiveCode })
    await expect(approvalRow).toBeVisible()
    await approvalRow.getByRole("button", { name: "审批" }).click()

    const approvalModal = adminPage.locator(".ant-modal-content").filter({ hasText: "处理销毁审批" }).first()
    await expect(approvalModal).toBeVisible()
    await approvalModal.getByPlaceholder("可补充审批说明").fill("E2E 销毁审批通过")
    await approvalModal.getByRole("button", { name: "提交审批" }).click()

    await expect(approvalRow).toContainText("已通过")

    await archivistPage.goto("/destruction/applications")
    await archivistPage.getByPlaceholder("按申请编号、档号、题名或申请人搜索").fill(archive.archiveCode)
    await archivistPage.getByRole("button", { name: "刷新列表" }).click()

    const executeRow = archivistPage.locator(".ant-table-tbody tr").filter({ hasText: archive.archiveCode })
    await expect(executeRow).toBeVisible()
    await expect(executeRow).toContainText("已通过")
    await executeRow.getByRole("button", { name: "执行销毁" }).click()

    const executeModal = archivistPage.locator(".ant-modal-content").filter({ hasText: "执行档案销毁" }).first()
    await expect(executeModal).toBeVisible()
    await executeModal.getByPlaceholder("请填写执行方式、现场情况和台账登记说明").fill("E2E 已完成销毁执行并登记台账")

    const uploadInputs = archivistPage.locator('input[type="file"]')
    await uploadInputs.nth(0).setInputFiles({
      name: "destroy-proof.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.from("e2e-destroy-proof"),
    })

    await executeModal.getByRole("button", { name: "确认执行" }).click()

    await expect(executeRow).toContainText("已执行销毁")

    await archivistPage.goto("/notifications/messages")
    await expect(archivistPage).toHaveURL(/\/notifications\/messages$/)

    const notificationRow = archivistPage
      .locator(".ant-table-tbody tr")
      .filter({ hasText: "档案销毁已执行" })
      .filter({ hasText: archive.archiveCode })
      .first()
    await expect(notificationRow).toBeVisible()
    await notificationRow.getByRole("button", { name: "查看业务" }).click()

    await expect(archivistPage).toHaveURL(/\/destruction\/applications(?:\?.*)?$/)
    await expect(archivistPage.getByText("销毁申请详情")).toBeVisible()

    const executedDetailDrawer = archivistPage.locator(".ant-drawer")
    await expect(executedDetailDrawer.getByText(archive.archiveCode, { exact: true })).toBeVisible()
    await expect(executedDetailDrawer.getByText("已执行销毁", { exact: true }).first()).toBeVisible()
    await expect(executedDetailDrawer.getByText("destroy-proof.pdf", { exact: true })).toBeVisible()
  } finally {
    await archivistContext.close()
    await adminContext.close()
  }
})
