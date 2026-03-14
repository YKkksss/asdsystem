import http, { type ApiResponse } from "@/api/http"


export interface DepartmentOption {
  id: number
  parent_id: number | null
  parent_name: string | null
  dept_code: string
  dept_name: string
  dept_path: string
  dept_level: number
  sort_order: number
  approver_user_id: number | null
  approver_user_name: string | null
  status: boolean
  remark: string | null
  created_at: string
  updated_at: string
}

export interface DepartmentPayload {
  parent_id?: number | null
  dept_code: string
  dept_name: string
  sort_order: number
  approver_user_id?: number | null
  status: boolean
  remark?: string | null
}

export async function fetchDepartments() {
  const response = await http.get<ApiResponse<DepartmentOption[]>>("/organizations/departments/")
  return response.data
}

export async function createDepartment(payload: DepartmentPayload) {
  const response = await http.post<ApiResponse<DepartmentOption>>("/organizations/departments/", payload)
  return response.data
}

export async function updateDepartment(departmentId: number, payload: DepartmentPayload) {
  const response = await http.put<ApiResponse<DepartmentOption>>(
    `/organizations/departments/${departmentId}/`,
    payload,
  )
  return response.data
}
