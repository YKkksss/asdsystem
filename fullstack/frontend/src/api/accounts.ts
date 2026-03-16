import http, { type ApiResponse } from "@/api/http"


export interface SystemPermissionItem {
  id: number
  parent_id: number | null
  parent_name: string | null
  permission_code: string
  permission_name: string
  permission_type: string
  module_name: string
  route_path: string | null
  sort_order: number
  status: boolean
  created_at: string
  updated_at: string
}

export interface PermissionTemplateItem {
  template_key: string
  role_code: string
  role_name: string
  template_name: string
  description: string
  permission_codes: string[]
}

export interface RoleItem {
  id: number
  role_code: string
  role_name: string
  data_scope: string
  status: boolean
  remark: string | null
  permission_ids?: number[]
  permissions: SystemPermissionItem[]
  created_at: string
  updated_at: string
}

export interface UserItem {
  id: number
  dept_id: number
  dept_name: string
  username: string
  real_name: string
  email: string | null
  phone: string | null
  security_clearance_level: string
  status: boolean
  failed_login_count: number
  last_failed_login_at: string | null
  lock_until_at: string | null
  last_login_at: string | null
  last_login_ip: string | null
  remark: string | null
  is_staff: boolean
  role_ids?: number[]
  roles: RoleItem[]
  created_at: string
  updated_at: string
}

export interface UserPayload {
  dept_id: number
  username: string
  password?: string
  real_name: string
  email?: string | null
  phone?: string | null
  security_clearance_level: string
  status: boolean
  remark?: string | null
  is_staff: boolean
  role_ids: number[]
}

export interface RolePayload {
  role_code: string
  role_name: string
  data_scope: string
  status: boolean
  remark?: string | null
  permission_ids: number[]
}

export interface SystemPermissionPayload {
  parent_id?: number | null
  permission_code: string
  permission_name: string
  permission_type: string
  module_name: string
  route_path?: string | null
  sort_order: number
  status: boolean
}

export async function fetchUsers() {
  const response = await http.get<ApiResponse<UserItem[]>>("/accounts/users/")
  return response.data
}

export async function createUser(payload: UserPayload) {
  const response = await http.post<ApiResponse<UserItem>>("/accounts/users/", payload)
  return response.data
}

export async function updateUser(userId: number, payload: UserPayload) {
  const response = await http.put<ApiResponse<UserItem>>(`/accounts/users/${userId}/`, payload)
  return response.data
}

export async function unlockUser(userId: number) {
  const response = await http.post<ApiResponse<null>>(`/auth/unlock/${userId}/`)
  return response.data
}

export async function fetchRoles() {
  const response = await http.get<ApiResponse<RoleItem[]>>("/accounts/roles/")
  return response.data
}

export async function createRole(payload: RolePayload) {
  const response = await http.post<ApiResponse<RoleItem>>("/accounts/roles/", payload)
  return response.data
}

export async function updateRole(roleId: number, payload: RolePayload) {
  const response = await http.put<ApiResponse<RoleItem>>(`/accounts/roles/${roleId}/`, payload)
  return response.data
}

export async function fetchPermissions() {
  const response = await http.get<ApiResponse<SystemPermissionItem[]>>("/accounts/permissions/")
  return response.data
}

export async function fetchPermissionTemplates() {
  const response = await http.get<ApiResponse<PermissionTemplateItem[]>>("/accounts/permission-templates/")
  return response.data
}

export async function createPermission(payload: SystemPermissionPayload) {
  const response = await http.post<ApiResponse<SystemPermissionItem>>("/accounts/permissions/", payload)
  return response.data
}

export async function updatePermission(permissionId: number, payload: SystemPermissionPayload) {
  const response = await http.put<ApiResponse<SystemPermissionItem>>(
    `/accounts/permissions/${permissionId}/`,
    payload,
  )
  return response.data
}
