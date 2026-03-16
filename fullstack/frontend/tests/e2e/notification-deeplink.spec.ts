import { expect, test } from "@playwright/test"

import {
  createAuthorizedApiContext,
  loginByUi,
  prepareDestroyApplication,
  prepareDigitizedArchive,
  prepareOnShelfArchive,
  triggerUserLock,
} from "./support"

interface ApiResponseShape<T> {
  data: T
  message: string
  code: number
}

interface BorrowApplicationResponse {
  id: number
}

interface NotificationListItem {
  id: number
  title: string
  content: string
  biz_type: string | null
  biz_id: number | null
}

interface UserListItem {
  id: number
  username: string
  real_name: string
}

const ACCOUNT_PASSWORD_MAP: Record<string, string> = {
  admin: "Admin12345",
  archivist: "Archivist12345",
  borrower: "Borrower12345",
  auditor: "Auditor12345",
}

async function sleep(ms: number) {
  await new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

async function createBorrowApplication() {
  const archive = await prepareOnShelfArchive({
    codePrefix: "E2E-NOTIFY",
    titlePrefix: "通知深链联调档案",
    summary: "用于通知中心深链定位测试",
  })

  const borrowerApi = await createAuthorizedApiContext("borrower", ACCOUNT_PASSWORD_MAP.borrower)
  try {
    const response = await borrowerApi.post("borrowing/applications/", {
      data: {
        archive_id: archive.archiveId,
        purpose: `通知深链联调 ${Date.now()}`,
        expected_return_at: new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString(),
      },
    })
    expect(response.ok()).toBeTruthy()
    const payload = await response.json() as ApiResponseShape<BorrowApplicationResponse>
    return {
      archiveId: archive.archiveId,
      archiveCode: archive.archiveCode,
      applicationId: payload.data.id,
    }
  } finally {
    await borrowerApi.dispose()
  }
}

async function waitForNotification(options: {
  username?: keyof typeof ACCOUNT_PASSWORD_MAP
  bizType?: string | null
  bizId?: number | null
  titleIncludes?: string
}): Promise<{ username: keyof typeof ACCOUNT_PASSWORD_MAP; notification: NotificationListItem }> {
  const usernames = options.username
    ? [options.username]
    : Object.keys(ACCOUNT_PASSWORD_MAP) as Array<keyof typeof ACCOUNT_PASSWORD_MAP>

  for (let attempt = 0; attempt < 12; attempt += 1) {
    for (const username of usernames) {
      const apiContext = await createAuthorizedApiContext(username, ACCOUNT_PASSWORD_MAP[username])
      try {
        const response = await apiContext.get("notifications/messages/")
        expect(response.ok()).toBeTruthy()
        const payload = await response.json() as ApiResponseShape<NotificationListItem[]>
        const targetNotification = payload.data.find((item) => {
          if (options.bizType !== undefined && item.biz_type !== options.bizType) {
            return false
          }
          if (options.bizId !== undefined && item.biz_id !== options.bizId) {
            return false
          }
          if (options.titleIncludes && !item.title.includes(options.titleIncludes)) {
            return false
          }
          return true
        })
        if (targetNotification) {
          return {
            username,
            notification: targetNotification,
          }
        }
      } finally {
        await apiContext.dispose()
      }
    }

    await sleep(300)
  }

  throw new Error(`未找到目标通知：${JSON.stringify(options)}`)
}

async function fetchUserByUsername(username: string): Promise<UserListItem> {
  const adminApi = await createAuthorizedApiContext("admin", ACCOUNT_PASSWORD_MAP.admin)
  try {
    const response = await adminApi.get("accounts/users/")
    expect(response.ok()).toBeTruthy()
    const payload = await response.json() as ApiResponseShape<UserListItem[]>
    const targetUser = payload.data.find((item) => item.username === username)
    if (!targetUser) {
      throw new Error(`未找到用户 ${username}`)
    }
    return targetUser
  } finally {
    await adminApi.dispose()
  }
}

async function exportDepartmentReportByApi(username: keyof typeof ACCOUNT_PASSWORD_MAP) {
  const apiContext = await createAuthorizedApiContext(username, ACCOUNT_PASSWORD_MAP[username])
  try {
    const response = await apiContext.get("reports/export/", {
      params: {
        report_type: "departments",
      },
    })
    expect(response.ok()).toBeTruthy()
    expect(response.headers()["content-type"]).toContain("text/csv")
  } finally {
    await apiContext.dispose()
  }
}

async function unlockUserByApi(userId: number) {
  const adminApi = await createAuthorizedApiContext("admin", ACCOUNT_PASSWORD_MAP.admin)
  try {
    const response = await adminApi.post(`auth/unlock/${userId}/`)
    expect(response.ok()).toBeTruthy()
  } finally {
    await adminApi.dispose()
  }
}

test("通知中心应能根据 notificationId 聚焦目标通知", async ({ page }) => {
  test.setTimeout(120000)

  const borrowApplication = await createBorrowApplication()
  const notificationOwner = await waitForNotification({
    bizType: "borrow_application",
    bizId: borrowApplication.applicationId,
  })

  await loginByUi(
    page,
    notificationOwner.username,
    ACCOUNT_PASSWORD_MAP[notificationOwner.username],
    `/notifications/messages?notificationId=${notificationOwner.notification.id}`,
  )

  await expect(page).toHaveURL(/\/notifications\/messages$/)
  const focusedRow = page.locator(".notification-row-focused").first()
  await expect(focusedRow).toBeVisible()
  await expect(focusedRow).toContainText(notificationOwner.notification.title)
  await expect(focusedRow).toContainText(borrowApplication.archiveCode)
})

test("销毁审批通知应能从通知中心直达销毁详情", async ({ page }) => {
  test.setTimeout(120000)

  const destroyApplication = await prepareDestroyApplication({
    codePrefix: "E2E-DESTROY-LINK",
    titlePrefix: "销毁通知深链联调档案",
    summary: "用于销毁审批通知深链联调测试",
  })
  const destroyNotification = await waitForNotification({
    username: "admin",
    bizType: "destroy_application",
    bizId: destroyApplication.applicationId,
  })

  await loginByUi(
    page,
    destroyNotification.username,
    ACCOUNT_PASSWORD_MAP[destroyNotification.username],
    `/notifications/messages?notificationId=${destroyNotification.notification.id}`,
  )

  await expect(page).toHaveURL(/\/notifications\/messages$/)
  const focusedRow = page.locator(".notification-row-focused").first()
  await expect(focusedRow).toBeVisible()
  await expect(focusedRow).toContainText("档案销毁待审批")
  await focusedRow.getByRole("button", { name: "查看业务" }).click()
  await expect(page).toHaveURL(/\/destruction\/applications$/)
  await expect(page.getByText("销毁申请详情", { exact: true })).toBeVisible()
  await expect(page.getByText(destroyApplication.applicationNo, { exact: true })).toBeVisible()
})

test("档案中心应能根据 archiveId 与 fileId 直达详情并高亮目标文件", async ({ page }) => {
  test.setTimeout(120000)

  const digitizedArchive = await prepareDigitizedArchive({
    codePrefix: "E2E-ARCHIVE-LINK",
    titlePrefix: "档案详情深链联调档案",
    summary: "用于档案详情文件高亮联调测试",
  })

  await loginByUi(
    page,
    "admin",
    ACCOUNT_PASSWORD_MAP.admin,
    `/archives/records?archiveId=${digitizedArchive.archiveId}&fileId=${digitizedArchive.fileId}`,
  )

  await expect(page).toHaveURL(/\/archives\/records$/)
  await expect(page.getByText("档案详情", { exact: true })).toBeVisible()
  const focusedFileCard = page.locator(".file-card-focused").first()
  await expect(focusedFileCard).toBeVisible()
  await expect(focusedFileCard).toContainText(digitizedArchive.fileName)
})

test("扫描任务详情应能根据 itemId 聚焦目标明细卡片", async ({ page }) => {
  test.setTimeout(120000)

  const digitizedArchive = await prepareDigitizedArchive({
    codePrefix: "E2E-SCAN-LINK",
    titlePrefix: "扫描任务深链联调档案",
    summary: "用于扫描任务明细高亮联调测试",
  })

  await loginByUi(
    page,
    "admin",
    ACCOUNT_PASSWORD_MAP.admin,
    `/digitization/scan-tasks/${digitizedArchive.taskId}?itemId=${digitizedArchive.itemId}`,
  )

  await expect(page).toHaveURL(new RegExp(`/digitization/scan-tasks/${digitizedArchive.taskId}$`))
  await expect(page.getByText("任务概览", { exact: true })).toBeVisible()
  const focusedItemCard = page.locator(".item-card-focused").first()
  await expect(focusedItemCard).toBeVisible()
  await expect(focusedItemCard).toContainText(digitizedArchive.archiveCode)
})

test("报表导出通知应能从通知中心直达报表中心", async ({ page }) => {
  test.setTimeout(120000)

  await exportDepartmentReportByApi("auditor")
  const reportNotification = await waitForNotification({
    username: "auditor",
    bizType: "report_export",
    titleIncludes: "报表导出已完成",
  })

  await loginByUi(
    page,
    reportNotification.username,
    ACCOUNT_PASSWORD_MAP[reportNotification.username],
    `/notifications/messages?notificationId=${reportNotification.notification.id}`,
  )

  await expect(page).toHaveURL(/\/notifications\/messages$/)
  const focusedRow = page.locator(".notification-row-focused").first()
  await expect(focusedRow).toBeVisible()
  await expect(focusedRow).toContainText("报表导出已完成")
  await focusedRow.getByRole("button", { name: "查看业务" }).click()
  await expect(page).toHaveURL(/\/reports\/center$/)
  await expect(page.getByText("部门借阅排行", { exact: true })).toBeVisible()
  await expect(page.getByText("档案利用率排行", { exact: true })).toBeVisible()
})

test("系统管理页应能根据 tab 与 userId 直达用户管理并打开编辑弹窗", async ({ page }) => {
  const borrower = await fetchUserByUsername("borrower")

  await loginByUi(
    page,
    "admin",
    ACCOUNT_PASSWORD_MAP.admin,
    `/system/management?tab=users&userId=${borrower.id}`,
  )

  await expect(page).toHaveURL(/\/system\/management$/)
  await expect(page.getByRole("tab", { name: "用户管理", selected: true })).toBeVisible()
  const editModal = page.locator(".ant-modal-wrap").filter({ hasText: "编辑用户" }).first()
  await expect(editModal).toBeVisible()
  await expect(editModal.getByPlaceholder("请输入登录账号")).toHaveValue(borrower.username)
  await expect(editModal.getByPlaceholder("请输入真实姓名")).toHaveValue(borrower.real_name)
})

test("通用系统通知应走通知中心兜底页且不展示业务跳转按钮", async ({ page }) => {
  test.setTimeout(120000)

  const borrower = await fetchUserByUsername("borrower")
  await triggerUserLock("borrower")
  await unlockUserByApi(borrower.id)
  const systemNotification = await waitForNotification({
    username: "borrower",
    bizType: null,
    titleIncludes: "账号已解锁",
  })

  await loginByUi(
    page,
    "borrower",
    ACCOUNT_PASSWORD_MAP.borrower,
    `/notifications/messages?notificationId=${systemNotification.notification.id}`,
  )

  await expect(page).toHaveURL(/\/notifications\/messages$/)
  const focusedRow = page.locator(".notification-row-focused").first()
  await expect(focusedRow).toBeVisible()
  await expect(focusedRow).toContainText("账号已解锁")
  await expect(focusedRow.getByRole("button", { name: "查看业务" })).toHaveCount(0)
})
