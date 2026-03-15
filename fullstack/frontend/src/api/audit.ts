import http, {
  type ApiResponse,
  type PaginatedResponseData,
  type PaginationQueryParams,
} from "@/api/http"


export interface AuditLog {
  id: number
  user_id: number | null
  username: string
  real_name: string
  module_name: string
  action_code: string
  biz_type: string | null
  biz_id: number | null
  target_repr: string | null
  result_status: "SUCCESS" | "FAILED" | "DENIED"
  description: string
  ip_address: string | null
  user_agent: string | null
  request_method: string | null
  request_path: string | null
  extra_data_json: Record<string, unknown>
  created_at: string
}

export interface AuditSummary {
  total_count: number
  today_count: number
  failed_count: number
  preview_count: number
  download_count: number
  module_counts: Array<{
    module_name: string
    count: number
  }>
}

export interface AuditLogQueryParams {
  keyword?: string
  module_name?: string
  action_code?: string
  result_status?: string
  username?: string
  biz_type?: string
}

export async function fetchAuditLogs(params?: AuditLogQueryParams) {
  const response = await http.get<ApiResponse<AuditLog[]>>("/audit/logs/", { params })
  return response.data
}

export async function fetchAuditLogsPage(params?: AuditLogQueryParams & PaginationQueryParams) {
  const response = await http.get<ApiResponse<PaginatedResponseData<AuditLog>>>("/audit/logs/", {
    params: {
      ...params,
      paginate: true,
    },
  })
  return response.data
}

export async function fetchAuditSummary() {
  const response = await http.get<ApiResponse<AuditSummary>>("/audit/summary/")
  return response.data
}
