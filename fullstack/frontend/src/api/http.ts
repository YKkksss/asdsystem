import axios from "axios"

import { useAuthStore } from "@/stores/auth"
import { clearStoredSession, readStoredAccessToken, readStoredRefreshToken } from "@/utils/session"

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v1"
const REFRESH_ENDPOINT = "/auth/refresh/"
const LOGIN_PAGE_PATH = "/login"

interface RetryableRequestConfig {
  _retry?: boolean
  headers?: Record<string, string> & { Authorization?: string }
  url?: string
}

const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
})

const refreshHttp = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
})

let refreshAccessTokenPromise: Promise<string> | null = null

function shouldSkipRefresh(url?: string) {
  if (!url) {
    return false
  }

  return ["/auth/login/", "/auth/logout/", REFRESH_ENDPOINT].some((path) => url.includes(path))
}

function redirectToLogin() {
  if (window.location.pathname === LOGIN_PAGE_PATH) {
    return
  }

  const redirectPath = `${window.location.pathname}${window.location.search}${window.location.hash}`
  const loginUrl = redirectPath && redirectPath !== "/"
    ? `${LOGIN_PAGE_PATH}?redirect=${encodeURIComponent(redirectPath)}`
    : LOGIN_PAGE_PATH
  window.location.replace(loginUrl)
}

function clearSessionAndRedirect() {
  try {
    const authStore = useAuthStore()
    authStore.clearSession()
  } catch {
    clearStoredSession()
  }
  redirectToLogin()
}

async function requestNewAccessToken() {
  const refreshToken = readStoredRefreshToken()
  if (!refreshToken) {
    throw new Error("缺少刷新令牌。")
  }

  if (!refreshAccessTokenPromise) {
    refreshAccessTokenPromise = refreshHttp
      .post<ApiResponse<{ access: string }>>(REFRESH_ENDPOINT, { refresh: refreshToken })
      .then((response) => {
        const nextAccessToken = response.data.data.access
        const authStore = useAuthStore()
        authStore.updateAccessToken(nextAccessToken)
        return nextAccessToken
      })
      .finally(() => {
        refreshAccessTokenPromise = null
      })
  }

  return refreshAccessTokenPromise
}

http.interceptors.request.use((config) => {
  const token = readStoredAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const response = error.response as { status?: number } | undefined
    const originalRequest = error.config as RetryableRequestConfig | undefined

    if (
      response?.status !== 401 ||
      !originalRequest ||
      originalRequest._retry ||
      shouldSkipRefresh(originalRequest.url)
    ) {
      return Promise.reject(error)
    }

    if (!readStoredRefreshToken()) {
      clearSessionAndRedirect()
      return Promise.reject(error)
    }

    originalRequest._retry = true

    try {
      const nextAccessToken = await requestNewAccessToken()
      originalRequest.headers = {
        ...(originalRequest.headers || {}),
        Authorization: `Bearer ${nextAccessToken}`,
      }
      return http(originalRequest)
    } catch (refreshError) {
      clearSessionAndRedirect()
      return Promise.reject(refreshError)
    }
  },
)

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export interface PaginationMeta {
  page: number
  page_size: number
  total: number
  total_pages: number
  has_next: boolean
  has_previous: boolean
}

export interface PaginatedResponseData<T> {
  items: T[]
  pagination: PaginationMeta
}

export interface PaginationQueryParams {
  page?: number
  page_size?: number
  paginate?: boolean
}

export function buildServerAssetUrl(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`
  if (/^https?:\/\//.test(API_BASE_URL)) {
    const serverOrigin = new URL(API_BASE_URL).origin
    return `${serverOrigin}${normalizedPath}`
  }
  return normalizedPath
}

export default http
