import type { LoginResponse } from "@/api/auth"

export const ALL_FALLBACK_ROLES = ["ADMIN", "ARCHIVIST", "BORROWER", "AUDITOR"] as const
export const ARCHIVE_CENTER_FALLBACK_ROLES = ["ADMIN", "ARCHIVIST"] as const
export const ARCHIVE_MANAGER_FALLBACK_ROLES = ["ADMIN", "ARCHIVIST"] as const
export const SYSTEM_MANAGER_FALLBACK_ROLES = ["ADMIN"] as const
export const REPORT_VIEW_FALLBACK_ROLES = ["ADMIN", "ARCHIVIST", "AUDITOR"] as const
export const AUDIT_VIEW_FALLBACK_ROLES = ["ADMIN", "AUDITOR"] as const
export const DESTRUCTION_VIEW_FALLBACK_ROLES = ["ADMIN", "ARCHIVIST"] as const
export const BORROW_CENTER_FALLBACK_ROLES = ["ADMIN", "ARCHIVIST", "BORROWER"] as const
export const BORROW_RETURN_FALLBACK_ROLES = ["ADMIN", "ARCHIVIST", "BORROWER"] as const
export const NOTIFICATION_FALLBACK_ROLES = ["ADMIN", "ARCHIVIST", "BORROWER", "AUDITOR"] as const

export interface AccessRule {
  permissionCodes?: readonly string[]
  fallbackRoles?: readonly string[]
}

export type AccessProfile = LoginResponse["profile"] | null | undefined

function buildPermissionCodeSet(profile: AccessProfile) {
  return new Set((profile?.permissions || []).map((item) => item.permission_code))
}

export function profileHasAnyRole(profile: AccessProfile, roleCodes: readonly string[]) {
  if (!roleCodes.length || !profile) {
    return false
  }

  return profile.roles.some((role) => roleCodes.includes(role.role_code))
}

export function profileHasAnyPermission(
  profile: AccessProfile,
  permissionCodes: readonly string[],
  fallbackRoles: readonly string[] = [],
) {
  if (!permissionCodes.length) {
    return true
  }

  const permissionCodeSet = buildPermissionCodeSet(profile)
  if (permissionCodeSet.size > 0) {
    return permissionCodes.some((permissionCode) => permissionCodeSet.has(permissionCode))
  }

  return profileHasAnyRole(profile, fallbackRoles)
}

export function profileHasAccess(profile: AccessProfile, rule: AccessRule = {}) {
  const { permissionCodes = [], fallbackRoles = [] } = rule

  if (permissionCodes.length) {
    return profileHasAnyPermission(profile, permissionCodes, fallbackRoles)
  }

  if (fallbackRoles.length) {
    return profileHasAnyRole(profile, fallbackRoles)
  }

  return Boolean(profile)
}
