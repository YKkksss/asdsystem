import http, {
  buildServerAssetUrl,
  type ApiResponse,
  type PaginatedResponseData,
  type PaginationQueryParams,
} from "@/api/http"
import { archiveUploadMaxSizeMb, buildUploadAccept, validateUploadFiles } from "@/utils/upload"

export const destroyAttachmentAllowedExtensions = ["pdf", "jpg", "jpeg", "png"] as const
export const destroyAttachmentAccept = buildUploadAccept(destroyAttachmentAllowedExtensions)
export const destroyAttachmentMaxSizeMb = archiveUploadMaxSizeMb

export function validateDestroyAttachmentFiles(files: File[]) {
  return validateUploadFiles(files, {
    allowedExtensions: destroyAttachmentAllowedExtensions,
    fileCategoryName: "销毁附件",
    maxSizeMb: destroyAttachmentMaxSizeMb,
  })
}


export interface DestroyApprovalRecord {
  id: number
  approver_id: number
  approver_name: string
  action: "APPROVE" | "REJECT"
  opinion: string | null
  approved_at: string
  created_at: string
  updated_at: string
}

export interface DestroyExecutionAttachment {
  id: number
  file_name: string
  file_path: string
  file_size: number
  uploaded_by: number
  created_at: string
  updated_at: string
}

export interface DestroyExecutionRecord {
  id: number
  application_id: number
  archive_id: number
  operator_id: number
  operator_name: string
  executed_at: string
  execution_note: string
  location_snapshot: string | null
  archive_snapshot_json: Record<string, unknown>
  attachments: DestroyExecutionAttachment[]
  created_at: string
  updated_at: string
}

export interface DestroyApplication {
  id: number
  application_no: string
  archive_id: number
  archive_code: string
  archive_title: string
  archive_status: string
  archive_security_level: string
  applicant_id: number
  applicant_name: string
  applicant_dept_id: number
  applicant_dept_name: string
  reason: string
  basis: string
  status: "PENDING_APPROVAL" | "APPROVED" | "REJECTED" | "EXECUTED"
  current_approver_id: number | null
  current_approver_name: string | null
  submitted_at: string | null
  approved_at: string | null
  rejected_at: string | null
  executed_at: string | null
  reject_reason: string | null
  can_approve: boolean
  can_execute: boolean
  created_by: number | null
  updated_by: number | null
  created_at: string
  updated_at: string
}

export interface DestroyApplicationDetail extends DestroyApplication {
  approval_records: DestroyApprovalRecord[]
  execution_record: DestroyExecutionRecord | null
}

export interface DestroyApplicationQueryParams {
  scope?: "mine" | "approval" | "execution" | "all"
  keyword?: string
  archive_code?: string
  status?: string
}

export interface DestroyApplicationPayload {
  archive_id: number
  reason: string
  basis: string
}

export interface DestroyApprovalPayload {
  action: "APPROVE" | "REJECT"
  opinion?: string
}

export interface DestroyExecutePayload {
  execution_note: string
  attachment_files?: File[]
}

export async function fetchDestroyApplications(params?: DestroyApplicationQueryParams) {
  const response = await http.get<ApiResponse<DestroyApplication[]>>("/destruction/applications/", { params })
  return response.data
}

export async function fetchDestroyApplicationsPage(
  params?: DestroyApplicationQueryParams & PaginationQueryParams,
) {
  const response = await http.get<ApiResponse<PaginatedResponseData<DestroyApplication>>>(
    "/destruction/applications/",
    {
      params: {
        ...params,
        paginate: true,
      },
    },
  )
  return response.data
}

export async function fetchDestroyApplicationDetail(applicationId: number) {
  const response = await http.get<ApiResponse<DestroyApplicationDetail>>(`/destruction/applications/${applicationId}/`)
  return response.data
}

export async function createDestroyApplication(payload: DestroyApplicationPayload) {
  const response = await http.post<ApiResponse<DestroyApplicationDetail>>("/destruction/applications/", payload)
  return response.data
}

export async function approveDestroyApplication(applicationId: number, payload: DestroyApprovalPayload) {
  const response = await http.post<ApiResponse<DestroyApplicationDetail>>(
    `/destruction/applications/${applicationId}/approve/`,
    payload,
  )
  return response.data
}

export async function executeDestroyApplication(applicationId: number, payload: DestroyExecutePayload) {
  const formData = new FormData()
  formData.append("execution_note", payload.execution_note)
  payload.attachment_files?.forEach((file) => {
    formData.append("attachment_files", file)
  })

  const response = await http.post<ApiResponse<DestroyApplicationDetail>>(
    `/destruction/applications/${applicationId}/execute/`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  )
  return response.data
}

export function buildDestroyAttachmentUrl(filePath: string) {
  return buildServerAssetUrl(`/media/${filePath}`)
}
