import http from "@/api/http"


export interface LoginPayload {
  username: string
  password: string
}

export interface LoginResponse {
  tokens: {
    access: string
    refresh: string
  }
  profile: {
    id: number
    username: string
    real_name: string
    email: string | null
    phone: string | null
    dept_id: number
    dept_name: string
    security_clearance_level: string
    status: boolean
    roles: Array<{
      id: number
      role_code: string
      role_name: string
      data_scope: string
    }>
    permissions: Array<{
      id: number
      permission_code: string
      permission_name: string
      permission_type: string
      module_name: string
      route_path: string | null
    }>
  }
}

export async function login(payload: LoginPayload) {
  const response = await http.post<{ code: number; message: string; data: LoginResponse }>(
    "/auth/login/",
    payload,
  )
  return response.data
}

export async function fetchProfile() {
  const response = await http.get("/auth/profile/")
  return response.data
}

export async function logout() {
  const response = await http.post<{ code: number; message: string; data: null }>("/auth/logout/")
  return response.data
}
