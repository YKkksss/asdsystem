import http, { type ApiResponse } from "@/api/http"


export interface ReportSummary {
  total_borrow_count: number
  overdue_count: number
  overdue_rate: number
  returned_count: number
  active_borrow_count: number
  total_archive_count: number
  utilized_archive_count: number
  archive_utilization_rate: number
}

export interface DepartmentReportRow {
  applicant_dept_id: number
  applicant_dept_name: string
  borrow_count: number
  overdue_count: number
  returned_count: number
  overdue_rate: number
}

export interface ArchiveUtilizationReportRow {
  rank: number
  archive_id: number
  archive_code: string
  archive_title: string
  security_level: string
  status: string
  carrier_type: string | null
  borrow_count: number
  overdue_count: number
  returned_count: number
  latest_borrowed_at: string | null
}

export interface ReportFilterParams {
  start_date?: string
  end_date?: string
  applicant_dept_id?: number
  archive_security_level?: string
  archive_status?: string
  carrier_type?: string
}

export interface ReportExportParams extends ReportFilterParams {
  report_type: "departments" | "archives"
}

function parseFileNameFromDisposition(disposition?: string) {
  if (!disposition) {
    return null
  }

  const utf8Matched = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Matched?.[1]) {
    return decodeURIComponent(utf8Matched[1])
  }

  const matched = disposition.match(/filename="?([^";]+)"?/i)
  return matched?.[1] || null
}

export async function fetchReportSummary(params?: ReportFilterParams) {
  const response = await http.get<ApiResponse<ReportSummary>>("/reports/summary/", { params })
  return response.data
}

export async function fetchDepartmentReports(params?: ReportFilterParams) {
  const response = await http.get<ApiResponse<DepartmentReportRow[]>>("/reports/departments/", { params })
  return response.data
}

export async function fetchArchiveReports(params?: ReportFilterParams) {
  const response = await http.get<ApiResponse<ArchiveUtilizationReportRow[]>>("/reports/archives/", { params })
  return response.data
}

export async function exportReportCsv(params: ReportExportParams) {
  const response = await http.get<Blob>("/reports/export/", {
    params,
    responseType: "blob",
  })

  return {
    blob: response.data,
    fileName: parseFileNameFromDisposition(response.headers["content-disposition"]) || `${params.report_type}-report.csv`,
  }
}
