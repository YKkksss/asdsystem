import http, { type ApiResponse } from "@/api/http"


export interface SystemHealthPayload {
  service: string
  status: string
  time: string
  version: string
}

export async function fetchSystemHealth() {
  const response = await http.get<ApiResponse<SystemHealthPayload>>("/system/health/")
  return response.data
}
