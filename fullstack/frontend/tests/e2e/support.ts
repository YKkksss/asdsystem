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

interface PrepareOnShelfArchiveOptions {
  codePrefix: string
  titlePrefix: string
  summary: string
}

export async function loginByUi(page: Page, username: string, password: string, targetPath = "/") {
  if (targetPath === "/") {
    await page.goto("/login")
  } else {
    await page.goto(targetPath)
    await page.waitForURL((url) => url.pathname === "/login" || url.pathname === targetPath, { timeout: 10000 })
  }

  if (!page.url().includes("/login")) {
    return
  }

  await page.getByPlaceholder("请输入用户名").fill(username)
  await page.getByPlaceholder("请输入密码").fill(password)
  await page.getByRole("button", { name: "登录系统" }).click()
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
  const apiContext = await createAuthorizedApiContext("admin", "Admin12345")
  const uniqueSuffix = Date.now()
  const archiveCode = `${options.codePrefix}-${uniqueSuffix}`
  const archiveTitle = `${options.titlePrefix} ${uniqueSuffix}`

  try {
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
        security_level: "INTERNAL",
        responsible_person: "E2E联调责任人",
        summary: options.summary,
        location_id: locationPayload.data.id,
        revision_remark: "E2E 初始化创建",
      },
    })
    expect(archiveResponse.ok()).toBeTruthy()
    const archivePayload = await archiveResponse.json() as ApiResponseShape<{ id: number }>

    const transitionToCatalogResponse = await apiContext.post(
      `archives/records/${archivePayload.data.id}/transition-status/`,
      {
        data: {
          next_status: "PENDING_CATALOG",
          remark: "E2E 流转到待编目",
        },
      },
    )
    expect(transitionToCatalogResponse.ok()).toBeTruthy()

    const transitionToShelfResponse = await apiContext.post(
      `archives/records/${archivePayload.data.id}/transition-status/`,
      {
        data: {
          next_status: "ON_SHELF",
          remark: "E2E 流转到已上架",
        },
      },
    )
    expect(transitionToShelfResponse.ok()).toBeTruthy()

    return {
      archiveId: archivePayload.data.id,
      archiveCode,
      archiveTitle,
    }
  } finally {
    await apiContext.dispose()
  }
}
