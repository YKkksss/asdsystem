import { expect, test } from "@playwright/test"

import { loginByUi, prepareDigitizedArchive } from "./support"

test("档案电子文件应能完成预览、下载与审计留痕闭环", async ({ browser }) => {
  const archive = await prepareDigitizedArchive({
    codePrefix: "E2E-FILE",
    titlePrefix: "E2E 文件访问档案",
    summary: "用于验证档案详情里的在线预览、下载确认与审计留痕闭环。",
  })
  const downloadPurpose = "E2E 下载用途校验"

  const archivistContext = await browser.newContext()
  const adminContext = await browser.newContext()
  const archivistPage = await archivistContext.newPage()
  const adminPage = await adminContext.newPage()

  try {
    await loginByUi(archivistPage, "archivist", "Archivist12345")
    await archivistPage.goto("/archives/records")
    await expect(archivistPage).toHaveURL(/\/archives\/records$/)

    await archivistPage.getByPlaceholder("按档号、题名、关键词、摘要或提取文本搜索").fill(archive.archiveCode)
    await archivistPage.getByRole("button", { name: "执行检索" }).click()

    const archiveRow = archivistPage.locator(".ant-table-tbody tr").filter({ hasText: archive.archiveCode })
    await expect(archiveRow).toBeVisible()
    await archiveRow.getByRole("button", { name: "查看详情" }).click()

    const archiveDetailDrawer = archivistPage.locator(".ant-drawer-content-wrapper:visible")
    await expect(archiveDetailDrawer).toBeVisible()
    await expect(archiveDetailDrawer.getByText(archive.archiveCode, { exact: true })).toBeVisible()

    const fileCard = archiveDetailDrawer.locator(".file-card").filter({ hasText: archive.fileName }).first()
    await expect(fileCard).toBeVisible()
    await expect(fileCard.getByText("ACTIVE", { exact: true })).toBeVisible()

    await fileCard.getByRole("button", { name: "在线预览" }).click()

    const previewModal = archivistPage.locator(".ant-modal-content").filter({ hasText: "文件在线预览" }).first()
    await expect(previewModal).toBeVisible()
    await expect(previewModal.locator(".preview-watermark")).toBeVisible()
    await expect(previewModal.locator(".preview-frame")).toBeVisible()
    await previewModal.locator(".ant-modal-close").click()
    await expect(archivistPage.locator(".preview-frame")).toHaveCount(0)

    await fileCard.getByRole("button", { name: "下载文件" }).click()

    const downloadModal = archivistPage.locator(".ant-modal-content").filter({ hasText: "下载确认" }).first()
    await expect(downloadModal).toBeVisible()
    await downloadModal.getByRole("button", { name: "确认下载" }).click()
    await expect(archivistPage.getByText("请填写下载用途。")).toBeVisible()

    await downloadModal
      .getByPlaceholder("请填写本次下载的业务用途，例如：工作核验、审批材料整理")
      .fill(downloadPurpose)
    await downloadModal.getByRole("button", { name: "确认下载" }).click()
    await expect(archivistPage.getByText("下载请求已提交，并已写入审计日志。")).toBeVisible()

    await loginByUi(adminPage, "admin", "Admin12345")
    await adminPage.goto("/audit/logs")
    await expect(adminPage).toHaveURL(/\/audit\/logs$/)

    await adminPage.getByPlaceholder("按用户、目标摘要或描述搜索").fill(archive.archiveCode)
    await adminPage.getByRole("button", { name: "刷新日志" }).click()

    const auditRows = adminPage.locator(".ant-table-tbody tr")
    await expect(auditRows.filter({ hasText: "申请预览票据" }).filter({ hasText: archive.archiveCode }).first()).toBeVisible()
    await expect(auditRows.filter({ hasText: "访问预览内容" }).filter({ hasText: archive.archiveCode }).first()).toBeVisible()
    await expect(auditRows.filter({ hasText: "申请下载票据" }).filter({ hasText: archive.archiveCode }).first()).toBeVisible()

    const downloadAccessRow = auditRows
      .filter({ hasText: "下载文件内容" })
      .filter({ hasText: archive.archiveCode })
      .first()
    await expect(downloadAccessRow).toBeVisible()

    const downloadApplyRow = auditRows
      .filter({ hasText: "申请下载票据" })
      .filter({ hasText: archive.archiveCode })
      .first()
    await downloadApplyRow.getByRole("button", { name: "查看详情" }).click()

    const auditDetailDrawer = adminPage.locator(".ant-drawer-content-wrapper:visible")
    await expect(auditDetailDrawer).toBeVisible()
    await expect(auditDetailDrawer.getByText(downloadPurpose)).toBeVisible()
  } finally {
    await archivistContext.close()
    await adminContext.close()
  }
})
