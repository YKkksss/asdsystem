import http, {
  buildServerAssetUrl,
  type ApiResponse,
  type PaginatedResponseData,
  type PaginationQueryParams,
} from "@/api/http"
import { archiveUploadMaxSizeMb, buildUploadAccept, validateUploadFiles } from "@/utils/upload"

export const borrowReturnAttachmentAllowedExtensions = ["pdf", "jpg", "jpeg", "png"] as const
export const borrowReturnAttachmentAccept = buildUploadAccept(borrowReturnAttachmentAllowedExtensions)
export const borrowReturnAttachmentMaxSizeMb = archiveUploadMaxSizeMb

export function validateBorrowReturnAttachmentFiles(files: File[]) {
  return validateUploadFiles(files, {
    allowedExtensions: borrowReturnAttachmentAllowedExtensions,
    fileCategoryName: "归还附件",
    maxSizeMb: borrowReturnAttachmentMaxSizeMb,
  })
}


export interface BorrowApprovalRecord {
  id: number
  approver_id: number
  approver_name: string
  action: "APPROVE" | "REJECT"
  opinion: string | null
  approved_at: string
  created_at: string
  updated_at: string
}

export interface BorrowCheckoutRecord {
  id: number
  application_id: number
  archive_id: number
  borrower_id: number
  borrower_name: string
  operator_id: number
  operator_name: string
  checkout_at: string
  expected_return_at: string
  location_snapshot: string | null
  checkout_note: string | null
  created_at: string
  updated_at: string
}

export interface BorrowReturnAttachment {
  id: number
  attachment_type: "PHOTO" | "HANDOVER_DOC"
  file_name: string
  file_path: string
  file_size: number
  uploaded_by: number
  created_at: string
}

export interface BorrowReturnRecord {
  id: number
  application_id: number
  archive_id: number
  returned_by_user_id: number
  returned_by_user_name: string
  received_by_user_id: number | null
  received_by_user_name: string | null
  return_status: "SUBMITTED" | "CONFIRMED" | "REJECTED"
  handover_type: "PHOTO" | "DOCUMENT" | "BOTH"
  handover_note: string | null
  returned_at: string
  confirmed_at: string | null
  location_after_return_id: number | null
  location_after_return_code: string | null
  confirm_note: string | null
  attachments: BorrowReturnAttachment[]
  created_at: string
  updated_at: string
}

export interface BorrowApplication {
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
  purpose: string
  expected_return_at: string
  status: string
  current_approver_id: number | null
  current_approver_name: string | null
  submitted_at: string | null
  approved_at: string | null
  rejected_at: string | null
  checkout_at: string | null
  returned_at: string | null
  reject_reason: string | null
  is_overdue: boolean
  overdue_days: number
  return_status: string | null
  can_approve: boolean
  can_checkout: boolean
  can_submit_return: boolean
  can_confirm_return: boolean
  created_by: number | null
  updated_by: number | null
  created_at: string
  updated_at: string
}

export interface BorrowApplicationDetail extends BorrowApplication {
  approval_records: BorrowApprovalRecord[]
  checkout_record: BorrowCheckoutRecord | null
  return_record: BorrowReturnRecord | null
}

export interface BorrowApplicationQueryParams {
  scope?: "mine" | "approval" | "checkout" | "return" | "all"
  keyword?: string
  archive_code?: string
  status?: string
  status_in?: string
}

export interface BorrowApplicationPayload {
  archive_id: number
  purpose: string
  expected_return_at: string
}

export interface BorrowApprovalPayload {
  action: "APPROVE" | "REJECT"
  opinion?: string
}

export interface BorrowCheckoutPayload {
  checkout_note?: string
}

export interface BorrowReturnSubmitPayload {
  handover_note?: string
  photo_files?: File[]
  handover_files?: File[]
}

export interface BorrowReturnConfirmPayload {
  approved: boolean
  location_after_return_id?: number | null
  confirm_note?: string
}

export async function fetchBorrowApplications(params?: BorrowApplicationQueryParams) {
  const response = await http.get<ApiResponse<BorrowApplication[]>>("/borrowing/applications/", { params })
  return response.data
}

export async function fetchBorrowApplicationsPage(
  params?: BorrowApplicationQueryParams & PaginationQueryParams,
) {
  const response = await http.get<ApiResponse<PaginatedResponseData<BorrowApplication>>>(
    "/borrowing/applications/",
    {
      params: {
        ...params,
        paginate: true,
      },
    },
  )
  return response.data
}

export async function fetchBorrowApplicationDetail(applicationId: number) {
  const response = await http.get<ApiResponse<BorrowApplicationDetail>>(`/borrowing/applications/${applicationId}/`)
  return response.data
}

export async function createBorrowApplication(payload: BorrowApplicationPayload) {
  const response = await http.post<ApiResponse<BorrowApplicationDetail>>("/borrowing/applications/", payload)
  return response.data
}

export async function approveBorrowApplication(applicationId: number, payload: BorrowApprovalPayload) {
  const response = await http.post<ApiResponse<BorrowApplicationDetail>>(
    `/borrowing/applications/${applicationId}/approve/`,
    payload,
  )
  return response.data
}

export async function checkoutBorrowApplication(applicationId: number, payload: BorrowCheckoutPayload) {
  const response = await http.post<ApiResponse<BorrowApplicationDetail>>(
    `/borrowing/applications/${applicationId}/checkout/`,
    payload,
  )
  return response.data
}

export async function submitBorrowReturn(applicationId: number, payload: BorrowReturnSubmitPayload) {
  const formData = new FormData()
  if (payload.handover_note) {
    formData.append("handover_note", payload.handover_note)
  }
  payload.photo_files?.forEach((file) => {
    formData.append("photo_files", file)
  })
  payload.handover_files?.forEach((file) => {
    formData.append("handover_files", file)
  })

  const response = await http.post<ApiResponse<BorrowApplicationDetail>>(
    `/borrowing/applications/${applicationId}/submit-return/`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  )
  return response.data
}

export async function confirmBorrowReturn(applicationId: number, payload: BorrowReturnConfirmPayload) {
  const response = await http.post<ApiResponse<BorrowApplicationDetail>>(
    `/borrowing/applications/${applicationId}/confirm-return/`,
    payload,
  )
  return response.data
}

export async function dispatchBorrowReminders() {
  const response = await http.post<ApiResponse<{ record_count: number }>>("/borrowing/reminders/dispatch/")
  return response.data
}

export function buildBorrowAttachmentUrl(filePath: string) {
  return buildServerAssetUrl(`/media/${filePath}`)
}
