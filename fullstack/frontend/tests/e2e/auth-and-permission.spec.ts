import { expect, test, type Page } from "@playwright/test"

import { createAuthorizedApiContext, loginByUi, logoutByUi, prepareOnShelfArchive } from "./support"

function getSidebar(page: Page) {
  return page.locator(".layout-sidebar")
}

async function expectSidebarTextVisible(page: Page, text: string) {
  await expect(getSidebar(page).getByText(text, { exact: true }).first()).toBeVisible()
}

async function expectSidebarTextHidden(page: Page, text: string) {
  await expect(getSidebar(page).getByText(text, { exact: true })).toHaveCount(0)
}

async function expectDashboardVisible(page: Page) {
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByText("核心指标", { exact: true })).toBeVisible()
  await expect(page.getByText("待办提醒", { exact: true })).toBeVisible()
  await expect(page.getByText("近 7 天趋势", { exact: true })).toBeVisible()
}

async function createBorrowApplicationForDashboard() {
  const archive = await prepareOnShelfArchive({
    codePrefix: "E2E-DASH",
    titlePrefix: "工作台待办联调档案",
    summary: "用于工作台待办直达链路验证",
  })

  const borrowerApi = await createAuthorizedApiContext("borrower", "Borrower12345")
  try {
    const expectedReturnAt = new Date(Date.now() + 60 * 60 * 1000).toISOString()
    const response = await borrowerApi.post("borrowing/applications/", {
      data: {
        archive_id: archive.archiveId,
        purpose: `工作台待办直达验证 ${Date.now()}`,
        expected_return_at: expectedReturnAt,
      },
    })
    expect(response.ok()).toBeTruthy()
    const payload = await response.json() as {
      data: {
        id: number
        application_no: string
      }
    }
    return payload.data
  } finally {
    await borrowerApi.dispose()
  }
}

test("管理员未登录访问系统管理时应先跳登录并在登录后回跳", async ({ page }) => {
  await loginByUi(page, "admin", "Admin12345", "/system/management")

  await expect(page).toHaveURL(/\/system\/management$/)
  await expect(page.getByRole("tab", { name: "用户管理" })).toBeVisible()
  await expect(page.getByRole("button", { name: "新建用户" })).toBeVisible()

  await expectSidebarTextVisible(page, "档案业务")
  await expectSidebarTextVisible(page, "借阅业务")
  await expectSidebarTextVisible(page, "统计监督")
  await expectSidebarTextVisible(page, "系统管理")

  await page.goto("/archives/records")
  await expect(page).toHaveURL(/\/archives\/records$/)
  await expect(page.getByRole("button", { name: "新建档案" })).toBeVisible()

  await page.goto("/audit/logs")
  await expect(page).toHaveURL(/\/audit\/logs$/)
  await expect(page.getByRole("button", { name: "刷新日志" })).toBeVisible()

  await logoutByUi(page)
  await expect(page.getByRole("button", { name: "登录系统" })).toBeVisible()
})

test("档案员应只看到档案与借阅相关菜单，并且不能进入借阅审批和系统管理", async ({ page }) => {
  await loginByUi(page, "archivist", "Archivist12345")

  await expectDashboardVisible(page)
  await expectSidebarTextVisible(page, "工作台")
  await expectSidebarTextVisible(page, "档案业务")
  await expectSidebarTextVisible(page, "借阅业务")
  await expectSidebarTextVisible(page, "统计监督")
  await expectSidebarTextHidden(page, "系统管理")

  await page.goto("/archives/records")
  await expect(page).toHaveURL(/\/archives\/records$/)
  await expect(page.getByRole("button", { name: "新建档案" })).toBeVisible()

  await page.goto("/borrowing/approvals")
  await expectDashboardVisible(page)

  await page.goto("/system/management")
  await expectDashboardVisible(page)
})

test("借阅人只应保留借阅闭环菜单，并且访问档案中心时应被拦回工作台", async ({ page }) => {
  await loginByUi(page, "borrower", "Borrower12345")

  await expectDashboardVisible(page)
  await expectSidebarTextVisible(page, "工作台")
  await expectSidebarTextVisible(page, "借阅业务")
  await expectSidebarTextHidden(page, "档案业务")
  await expectSidebarTextHidden(page, "统计监督")
  await expectSidebarTextHidden(page, "系统管理")

  await page.goto("/borrowing/applications")
  await expect(page).toHaveURL(/\/borrowing\/applications$/)
  await expect(page.getByText("新建借阅申请")).toBeVisible()
  await expect(page.getByRole("button", { name: "提交申请" })).toBeVisible()

  await page.goto("/archives/records")
  await expectDashboardVisible(page)
})

test("审计员应可进入报表和审计页面，但不能进入档案中心和销毁中心", async ({ page }) => {
  await loginByUi(page, "auditor", "Auditor12345")

  await expectDashboardVisible(page)
  await expectSidebarTextVisible(page, "工作台")
  await expectSidebarTextVisible(page, "借阅业务")
  await expectSidebarTextVisible(page, "统计监督")
  await expectSidebarTextHidden(page, "档案业务")
  await expectSidebarTextHidden(page, "系统管理")

  await page.goto("/reports/center")
  await expect(page).toHaveURL(/\/reports\/center$/)
  await expect(page.getByRole("button", { name: "刷新报表" })).toBeVisible()

  await page.goto("/audit/logs")
  await expect(page).toHaveURL(/\/audit\/logs$/)
  await expect(page.getByRole("button", { name: "刷新日志" })).toBeVisible()

  await page.goto("/destruction/applications")
  await expectDashboardVisible(page)
})

test("工作台待办明细应能直达审批、出库和归还操作", async ({ page }) => {
  test.setTimeout(120000)
  const borrowApplication = await createBorrowApplicationForDashboard()
  const pendingTaskBoard = page.locator(".list-board").filter({ hasText: "近期待办明细" })

  await loginByUi(page, "admin", "Admin12345")
  await expectDashboardVisible(page)
  await pendingTaskBoard.getByText(borrowApplication.application_no, { exact: true }).click()
  await expect(page).toHaveURL(/\/borrowing\/approvals/)
  const approvalDialog = page.locator(".ant-modal-wrap").filter({
    hasText: `当前处理单号：${borrowApplication.application_no}`,
  })
  await expect(approvalDialog).toBeVisible()
  await page.getByRole("button", { name: "确认通过" }).click()
  await expect(approvalDialog).toBeHidden()
  await logoutByUi(page)

  await loginByUi(page, "archivist", "Archivist12345")
  await expectDashboardVisible(page)
  await pendingTaskBoard.getByText(borrowApplication.application_no, { exact: true }).click()
  await expect(page).toHaveURL(/\/borrowing\/checkout/)
  const checkoutDialog = page.locator(".ant-modal-wrap").filter({
    hasText: borrowApplication.application_no,
  })
  await expect(checkoutDialog).toBeVisible()
  await page.getByRole("button", { name: "确认出库" }).click()
  await expect(checkoutDialog).toBeHidden()
  await logoutByUi(page)

  await loginByUi(page, "borrower", "Borrower12345")
  await expectDashboardVisible(page)
  await pendingTaskBoard.getByText(borrowApplication.application_no, { exact: true }).click()
  await expect(page).toHaveURL(/\/borrowing\/returns/)
  const returnDialog = page.locator(".ant-modal-wrap").filter({
    hasText: `归还单号：${borrowApplication.application_no}`,
  })
  await expect(returnDialog).toBeVisible()
  await returnDialog.locator(".ant-modal-close").click()
  await expect(returnDialog).toBeHidden()
})
