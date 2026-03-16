import { expect, type APIRequestContext, type Page, request as playwrightRequest } from "@playwright/test"

const BACKEND_API_BASE_URL = "http://127.0.0.1:8001/api/v1/"

interface LoginResponseData {
  tokens: {
    access: string
    refresh: string
  }
}

interface ApiResponseShape<T> {
  data: T
  message: string
  code: number
}

export interface OnShelfArchiveSetupResult {
  archiveId: number
  archiveCode: string
  archiveTitle: string
}

export interface DigitizedArchiveSetupResult extends OnShelfArchiveSetupResult {
  fileName: string
  fileId: number
  taskId: number
  itemId: number
}

export interface DestroyApplicationSetupResult extends OnShelfArchiveSetupResult {
  applicationId: number
  applicationNo: string
}

export interface ArchiveViewerAccountResult {
  username: string
  password: string
}

interface PrepareOnShelfArchiveOptions {
  codePrefix: string
  titlePrefix: string
  summary: string
  securityLevel?: string
  responsiblePerson?: string
}

interface PreparedArchiveDraftResult extends OnShelfArchiveSetupResult {
  locationId: number
}

interface ScanTaskDetailResponse {
  id: number
  items: Array<{
    id: number
  }>
}

interface DestroyApplicationResponse {
  id: number
  application_no: string
}

interface ArchiveDetailResponse {
  status: string
  files: Array<{
    id: number
    file_name: string
    status: string
  }>
}

interface UserListItem {
  id: number
  username: string
  dept_id: number
}

interface RoleListItem {
  id: number
  role_code: string
  permissions: Array<{
    id: number
  }>
}

const E2E_PREVIEW_PDF_BASE64 =
  "JVBERi0xLjcKJcK1wrYKCjEgMCBvYmoKPDwvVHlwZS9DYXRhbG9nL1BhZ2VzIDIgMCBSPj4KZW5kb2JqCgoyIDAgb2JqCjw8L1R5cGUvUGFnZXMvQ291bnQgMS9LaWRzWzQgMCBSXT4+CmVuZG9iagoKMyAwIG9iago8PC9Gb250PDwvaGVsdiA1IDAgUj4+Pj4KZW5kb2JqCgo0IDAgb2JqCjw8L1R5cGUvUGFnZS9NZWRpYUJveFswIDAgNTk1IDg0Ml0vUm90YXRlIDAvUmVzb3VyY2VzIDMgMCBSL1BhcmVudCAyIDAgUi9Db250ZW50c1s2IDAgUl0+PgplbmRvYmoKCjUgMCBvYmoKPDwvVHlwZS9Gb250L1N1YnR5cGUvVHlwZTEvQmFzZUZvbnQvSGVsdmV0aWNhL0VuY29kaW5nL1dpbkFuc2lFbmNvZGluZz4+CmVuZG9iagoKNiAwIG9iago8PC9MZW5ndGggODA+PgpzdHJlYW0KCnEKQlQKMSAwIDAgMSA3MiA3NzAgVG0KL2hlbHYgMTEgVGYgWzw0NTMyNDUyMDUwNzI2NTc2Njk2NTc3MjA0NjY5NmM2NT5dVEoKRVQKUQoKZW5kc3RyZWFtCmVuZG9iagoKeHJlZgowIDcKMDAwMDAwMDAwMCA2NTUzNSBmIAowMDAwMDAwMDE2IDAwMDAwIG4gCjAwMDAwMDAwNjIgMDAwMDAgbiAKMDAwMDAwMDExNCAwMDAwMCBuIAowMDAwMDAwMTU1IDAwMDAwIG4gCjAwMDAwMDAyNjIgMDAwMDAgbiAKMDAwMDAwMDM1MSAwMDAwMCBuIAoKdHJhaWxlcgo8PC9TaXplIDcvUm9vdCAxIDAgUi9JRFs8QzI5QkMzQTk3RjYyQzM4REMyQUIyRUMyOEZDMjg3QzM+PEYwRUE3RDI2OEZCMjJFOUU0NzA2QUYwNTQwNDIzMDVGPl0+PgpzdGFydHhyZWYKNDgwCiUlRU9GCg=="

function sleep(ms: number) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

function buildPdfFixtureBuffer() {
  return Buffer.from(E2E_PREVIEW_PDF_BASE64, "base64")
}

async function createArchiveDraft(
  apiContext: APIRequestContext,
  options: PrepareOnShelfArchiveOptions,
): Promise<PreparedArchiveDraftResult> {
  const uniqueSuffix = Date.now()
  const archiveCode = `${options.codePrefix}-${uniqueSuffix}`
  const archiveTitle = `${options.titlePrefix} ${uniqueSuffix}`

  const locationResponse = await apiContext.post("archives/storage-locations/", {
    data: {
      warehouse_name: "E2E库房",
      area_name: "联调区",
      cabinet_code: `G${String(uniqueSuffix).slice(-3)}`,
      rack_code: "J01",
      layer_code: "L01",
      box_code: "H01",
      status: true,
      remark: `${options.titlePrefix}基础位置`,
    },
  })
  expect(locationResponse.ok()).toBeTruthy()
  const locationPayload = await locationResponse.json() as ApiResponseShape<{ id: number }>

  const archiveResponse = await apiContext.post("archives/records/", {
    data: {
      archive_code: archiveCode,
      title: archiveTitle,
      year: new Date().getFullYear(),
      retention_period: "长期",
      security_level: options.securityLevel || "INTERNAL",
      responsible_person: options.responsiblePerson || "E2E联调责任人",
      summary: options.summary,
      location_id: locationPayload.data.id,
      revision_remark: "E2E 初始化创建",
    },
  })
  expect(archiveResponse.ok()).toBeTruthy()
  const archivePayload = await archiveResponse.json() as ApiResponseShape<{ id: number }>

  return {
    archiveId: archivePayload.data.id,
    archiveCode,
    archiveTitle,
    locationId: locationPayload.data.id,
  }
}

async function waitForDigitizedFileReady(apiContext: APIRequestContext, archiveId: number, fileName: string) {
  for (let attempt = 0; attempt < 10; attempt += 1) {
    const archiveDetailResponse = await apiContext.get(`archives/records/${archiveId}/`)
    expect(archiveDetailResponse.ok()).toBeTruthy()
    const archiveDetailPayload = await archiveDetailResponse.json() as ApiResponseShape<ArchiveDetailResponse>
    const targetFile = archiveDetailPayload.data.files.find((item) => item.file_name === fileName)

    if (archiveDetailPayload.data.status === "PENDING_CATALOG" && targetFile?.status === "ACTIVE") {
      return targetFile.id
    }

    await sleep(300)
  }

  throw new Error(`等待数字化文件处理完成超时，archiveId=${archiveId}，fileName=${fileName}`)
}

export async function loginByUi(page: Page, username: string, password: string, targetPath = "/") {
  if (targetPath === "/") {
    await page.goto("/login")
  } else {
    await page.goto(targetPath)
  }

  const loginButton = page.getByRole("button", { name: "登录系统" })

  try {
    await expect(loginButton).toBeVisible({ timeout: 5000 })
  } catch {
    await page.waitForURL((url) => url.pathname === targetPath, { timeout: 10000 })
    return
  }

  await page.getByPlaceholder("请输入用户名").fill(username)
  await page.getByPlaceholder("请输入密码").fill(password)
  await loginButton.click()
  await page.waitForURL((url) => url.pathname !== "/login", { timeout: 10000 })
}

export async function logoutByUi(page: Page) {
  const visibleDrawers = page.locator(".ant-drawer-content-wrapper:visible")
  if (await visibleDrawers.count()) {
    const drawerCloseButton = page.locator(".ant-drawer-content-wrapper:visible .ant-drawer-close")
    if (await drawerCloseButton.count()) {
      await drawerCloseButton.first().click()
    } else {
      await page.keyboard.press("Escape")
    }
    await expect(visibleDrawers).toHaveCount(0, { timeout: 5000 })
  }

  await page.getByRole("button", { name: "退出登录" }).click()
  await expect(page).toHaveURL(/\/login$/)
}

export async function createAuthorizedApiContext(username: string, password: string): Promise<APIRequestContext> {
  const apiContext = await playwrightRequest.newContext({
    baseURL: BACKEND_API_BASE_URL,
  })

  const loginResponse = await apiContext.post("auth/login/", {
    data: {
      username,
      password,
    },
  })

  expect(loginResponse.ok()).toBeTruthy()
  const loginPayload = await loginResponse.json() as ApiResponseShape<LoginResponseData>

  await apiContext.dispose()

  return playwrightRequest.newContext({
    baseURL: BACKEND_API_BASE_URL,
    extraHTTPHeaders: {
      Authorization: `Bearer ${loginPayload.data.tokens.access}`,
    },
  })
}

export async function prepareOnShelfArchive(
  options: PrepareOnShelfArchiveOptions,
): Promise<OnShelfArchiveSetupResult> {
  const apiContext = await createAuthorizedApiContext("archivist", "Archivist12345")

  try {
    const archiveDraft = await createArchiveDraft(apiContext, options)

    const transitionToCatalogResponse = await apiContext.post(
      `archives/records/${archiveDraft.archiveId}/transition-status/`,
      {
        data: {
          next_status: "PENDING_CATALOG",
          remark: "E2E 流转到待编目",
        },
      },
    )
    expect(transitionToCatalogResponse.ok()).toBeTruthy()

    const transitionToShelfResponse = await apiContext.post(
      `archives/records/${archiveDraft.archiveId}/transition-status/`,
      {
        data: {
          next_status: "ON_SHELF",
          remark: "E2E 流转到已上架",
        },
      },
    )
    expect(transitionToShelfResponse.ok()).toBeTruthy()

    return {
      archiveId: archiveDraft.archiveId,
      archiveCode: archiveDraft.archiveCode,
      archiveTitle: archiveDraft.archiveTitle,
    }
  } finally {
    await apiContext.dispose()
  }
}

export async function prepareDigitizedArchive(
  options: PrepareOnShelfArchiveOptions,
): Promise<DigitizedArchiveSetupResult> {
  const apiContext = await createAuthorizedApiContext("archivist", "Archivist12345")

  try {
    const archiveDraft = await createArchiveDraft(apiContext, options)
    const scanTaskResponse = await apiContext.post("digitization/scan-tasks/", {
      data: {
        task_name: `${archiveDraft.archiveCode} 数字化联调任务`,
        archive_ids: [archiveDraft.archiveId],
        remark: "E2E 电子文件预览下载联调",
      },
    })
    expect(scanTaskResponse.ok()).toBeTruthy()
    const scanTaskPayload = await scanTaskResponse.json() as ApiResponseShape<ScanTaskDetailResponse>

    const fileName = `${archiveDraft.archiveCode.toLowerCase()}-preview.pdf`
    const uploadResponse = await apiContext.post(
      `digitization/scan-task-items/${scanTaskPayload.data.items[0].id}/upload-files/`,
      {
        multipart: {
          files: {
            name: fileName,
            mimeType: "application/pdf",
            buffer: buildPdfFixtureBuffer(),
          },
        },
      },
    )
    expect(uploadResponse.ok()).toBeTruthy()

    const fileId = await waitForDigitizedFileReady(apiContext, archiveDraft.archiveId, fileName)

    const transitionToShelfResponse = await apiContext.post(
      `archives/records/${archiveDraft.archiveId}/transition-status/`,
      {
        data: {
          next_status: "ON_SHELF",
          remark: "E2E 数字化完成后上架",
        },
      },
    )
    expect(transitionToShelfResponse.ok()).toBeTruthy()

    return {
      archiveId: archiveDraft.archiveId,
      archiveCode: archiveDraft.archiveCode,
      archiveTitle: archiveDraft.archiveTitle,
      fileName,
      fileId,
      taskId: scanTaskPayload.data.id,
      itemId: scanTaskPayload.data.items[0].id,
    }
  } finally {
    await apiContext.dispose()
  }
}

export async function createLowClearanceArchiveViewer(): Promise<ArchiveViewerAccountResult> {
  const adminApi = await createAuthorizedApiContext("admin", "Admin12345")
  const password = "Viewer12345"
  const uniqueSuffix = Date.now()
  const username = `archive_viewer_${uniqueSuffix}`
  const roleCode = `E2E_ARCHIVE_VIEWER_${uniqueSuffix}`

  try {
    const usersResponse = await adminApi.get("accounts/users/")
    expect(usersResponse.ok()).toBeTruthy()
    const usersPayload = await usersResponse.json() as ApiResponseShape<UserListItem[]>
    const archivistUser = usersPayload.data.find((item) => item.username === "archivist")
    if (!archivistUser) {
      throw new Error("未找到档案员基础账号，无法创建低密级档案查看账号。")
    }

    const rolesResponse = await adminApi.get("accounts/roles/")
    expect(rolesResponse.ok()).toBeTruthy()
    const rolesPayload = await rolesResponse.json() as ApiResponseShape<RoleListItem[]>
    const archivistRole = rolesPayload.data.find((item) => item.role_code === "ARCHIVIST")
    if (!archivistRole) {
      throw new Error("未找到档案员角色，无法创建低密级档案查看账号。")
    }

    const createRoleResponse = await adminApi.post("accounts/roles/", {
      data: {
        role_code: roleCode,
        role_name: "E2E低密级档案查看员",
        data_scope: "ALL",
        status: true,
        permission_ids: archivistRole.permissions.map((item) => item.id),
      },
    })
    expect(createRoleResponse.ok()).toBeTruthy()
    const createRolePayload = await createRoleResponse.json() as ApiResponseShape<{ id: number }>

    const createUserResponse = await adminApi.post("accounts/users/", {
      data: {
        dept_id: archivistUser.dept_id,
        username,
        password,
        real_name: "低密级档案查看员",
        status: true,
        role_ids: [createRolePayload.data.id],
        security_clearance_level: "INTERNAL",
        is_staff: true,
      },
    })
    expect(createUserResponse.ok()).toBeTruthy()

    return {
      username,
      password,
    }
  } finally {
    await adminApi.dispose()
  }
}

export async function prepareDestroyApplication(
  options: PrepareOnShelfArchiveOptions & {
    reason?: string
    basis?: string
  },
): Promise<DestroyApplicationSetupResult> {
  const apiContext = await createAuthorizedApiContext("archivist", "Archivist12345")

  try {
    const archiveDraft = await createArchiveDraft(apiContext, options)

    const transitionToCatalogResponse = await apiContext.post(
      `archives/records/${archiveDraft.archiveId}/transition-status/`,
      {
        data: {
          next_status: "PENDING_CATALOG",
          remark: "E2E 销毁流程流转到待编目",
        },
      },
    )
    expect(transitionToCatalogResponse.ok()).toBeTruthy()

    const transitionToShelfResponse = await apiContext.post(
      `archives/records/${archiveDraft.archiveId}/transition-status/`,
      {
        data: {
          next_status: "ON_SHELF",
          remark: "E2E 销毁流程流转到已上架",
        },
      },
    )
    expect(transitionToShelfResponse.ok()).toBeTruthy()

    const destroyApplicationResponse = await apiContext.post("destruction/applications/", {
      data: {
        archive_id: archiveDraft.archiveId,
        reason: options.reason || "E2E 销毁深链联调原因",
        basis: options.basis || "E2E 销毁深链联调依据",
      },
    })
    expect(destroyApplicationResponse.ok()).toBeTruthy()
    const destroyApplicationPayload = await destroyApplicationResponse.json() as ApiResponseShape<DestroyApplicationResponse>

    return {
      archiveId: archiveDraft.archiveId,
      archiveCode: archiveDraft.archiveCode,
      archiveTitle: archiveDraft.archiveTitle,
      applicationId: destroyApplicationPayload.data.id,
      applicationNo: destroyApplicationPayload.data.application_no,
    }
  } finally {
    await apiContext.dispose()
  }
}

export async function triggerUserLock(username: string, failedPassword = "WrongPassword123") {
  const apiContext = await playwrightRequest.newContext({
    baseURL: BACKEND_API_BASE_URL,
  })

  try {
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const response = await apiContext.post("auth/login/", {
        data: {
          username,
          password: failedPassword,
        },
      })
      const expectedStatus = attempt < 2 ? 400 : 423
      expect(response.status()).toBe(expectedStatus)
    }
  } finally {
    await apiContext.dispose()
  }
}
