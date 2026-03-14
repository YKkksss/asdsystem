import http, { type ApiResponse } from "@/api/http"
import { archiveUploadMaxSizeMb, buildUploadAccept, validateUploadFiles } from "@/utils/upload"

export const scanUploadAllowedExtensions = ["pdf", "jpg", "jpeg", "png", "tif", "tiff"] as const
export const scanUploadAccept = buildUploadAccept(scanUploadAllowedExtensions)
export const scanUploadMaxSizeMb = archiveUploadMaxSizeMb

export function validateScanUploadFiles(files: File[]) {
  return validateUploadFiles(files, {
    allowedExtensions: scanUploadAllowedExtensions,
    fileCategoryName: "扫描文件",
    maxSizeMb: scanUploadMaxSizeMb,
  })
}

export interface ScanTaskFile {
  id: number
  file_name: string
  file_path: string
  thumbnail_path: string | null
  file_ext: string
  mime_type: string | null
  file_size: number
  page_count: number | null
  file_source: string
  sort_order: number
  extracted_text: string | null
  status: string
  uploaded_by: number
  created_at: string
}

export interface ScanTaskItem {
  id: number
  archive_id: number
  archive_code: string
  archive_title: string
  archive_status: string
  assignee_user_id: number
  status: string
  uploaded_file_count: number
  last_uploaded_at: string | null
  error_message: string | null
  files: ScanTaskFile[]
  created_at: string
  updated_at: string
}

export interface ScanTask {
  id: number
  task_no: string
  task_name: string
  assigned_user_id: number
  assigned_user_name: string | null
  assigned_by: number
  status: string
  total_count: number
  completed_count: number
  failed_count: number
  started_at: string | null
  finished_at: string | null
  remark: string | null
  created_by: number | null
  updated_by: number | null
  created_at: string
  updated_at: string
}

export interface ScanTaskDetail extends ScanTask {
  items: ScanTaskItem[]
}

export interface ScanTaskCreatePayload {
  task_name: string
  assigned_user_id?: number
  archive_ids: number[]
  remark?: string
}

export interface ScanTaskAssignee {
  id: number
  username: string
  real_name: string
  dept_id: number
}

export async function fetchScanTasks() {
  const response = await http.get<ApiResponse<ScanTask[]>>("/digitization/scan-tasks/")
  return response.data
}

export async function fetchScanTaskDetail(taskId: number) {
  const response = await http.get<ApiResponse<ScanTaskDetail>>(`/digitization/scan-tasks/${taskId}/`)
  return response.data
}

export async function createScanTask(payload: ScanTaskCreatePayload) {
  const response = await http.post<ApiResponse<ScanTaskDetail>>("/digitization/scan-tasks/", payload)
  return response.data
}

export async function fetchScanTaskAssignees() {
  const response = await http.get<ApiResponse<ScanTaskAssignee[]>>("/digitization/scan-task-assignees/")
  return response.data
}

export async function uploadScanTaskItemFiles(itemId: number, files: File[]) {
  const formData = new FormData()
  files.forEach((file) => {
    formData.append("files", file)
  })
  const response = await http.post<ApiResponse<ScanTaskDetail>>(
    `/digitization/scan-task-items/${itemId}/upload-files/`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  )
  return response.data
}
