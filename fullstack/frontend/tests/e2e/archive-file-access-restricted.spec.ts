import { expect, test } from "@playwright/test"

import { createLowClearanceArchiveViewer, loginByUi, prepareDigitizedArchive } from "./support"

test("低密级账号查看高密级档案时应看到脱敏结果且无文件访问入口", async ({ page }) => {
  const archive = await prepareDigitizedArchive({
    codePrefix: "E2E-FILE-MASK",
    titlePrefix: "E2E 文件脱敏档案",
    summary: "用于验证档案详情中的脱敏展示与文件访问限制。",
    securityLevel: "SECRET",
    responsiblePerson: "借阅人示例账号",
  })
  const archiveViewer = await createLowClearanceArchiveViewer()

  await loginByUi(page, archiveViewer.username, archiveViewer.password)
  await page.goto("/archives/records")
  await expect(page).toHaveURL(/\/archives\/records$/)

  await page.getByPlaceholder("按档号、题名、关键词、摘要或提取文本搜索").fill(archive.archiveCode)
  await page.getByRole("button", { name: "执行检索" }).click()

  const archiveRow = page.locator(".ant-table-tbody tr").filter({ hasText: archive.archiveCode })
  await expect(archiveRow).toBeVisible()
  await expect(archiveRow.getByText("已脱敏", { exact: true })).toBeVisible()
  await archiveRow.getByRole("button", { name: "查看详情" }).click()

  const archiveDetailDrawer = page.locator(".ant-drawer-content-wrapper:visible")
  await expect(archiveDetailDrawer).toBeVisible()
  await expect(archiveDetailDrawer.getByText("当前账号密级不足，摘要、责任者、文件与实体精确位置已由后端脱敏。")).toBeVisible()
  await expect(archiveDetailDrawer.getByText("权限不足，摘要已脱敏。")).toBeVisible()
  await expect(archiveDetailDrawer.getByText("权限不足，责任者已脱敏。")).toBeVisible()
  await expect(archiveDetailDrawer.getByText("当前账号无权查看文件预览入口和提取文本。")).toBeVisible()
  await expect(archiveDetailDrawer.getByRole("button", { name: "在线预览" })).toHaveCount(0)
  await expect(archiveDetailDrawer.getByRole("button", { name: "下载文件" })).toHaveCount(0)
})
