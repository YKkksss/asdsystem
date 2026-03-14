const ACCESS_TOKEN_KEY = "asd_system_access_token"
const REFRESH_TOKEN_KEY = "asd_system_refresh_token"
const PROFILE_KEY = "asd_system_profile"

export function readStoredAccessToken() {
  return window.localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function readStoredRefreshToken() {
  return window.localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function readStoredProfile<T>() {
  const rawValue = window.localStorage.getItem(PROFILE_KEY)
  if (!rawValue) {
    return null
  }

  try {
    return JSON.parse(rawValue) as T
  } catch {
    return null
  }
}

export function writeStoredAccessToken(token: string | null) {
  if (token) {
    window.localStorage.setItem(ACCESS_TOKEN_KEY, token)
    return
  }
  window.localStorage.removeItem(ACCESS_TOKEN_KEY)
}

export function writeStoredRefreshToken(token: string | null) {
  if (token) {
    window.localStorage.setItem(REFRESH_TOKEN_KEY, token)
    return
  }
  window.localStorage.removeItem(REFRESH_TOKEN_KEY)
}

export function writeStoredProfile(profile: unknown | null) {
  if (profile) {
    window.localStorage.setItem(PROFILE_KEY, JSON.stringify(profile))
    return
  }
  window.localStorage.removeItem(PROFILE_KEY)
}

export function clearStoredSession() {
  writeStoredAccessToken(null)
  writeStoredRefreshToken(null)
  writeStoredProfile(null)
}
