import http, {
  buildServerAssetUrl,
  type ApiResponse,
  type PaginatedResponseData,
  type PaginationQueryParams,
} from "@/api/http"


export interface ArchiveStorageLocation {
  id: number
  warehouse_name: string
  area_name: string | null
  cabinet_code: string
  rack_code: string
  layer_code: string
  box_code: string
  full_location_code: string
  status: boolean
  remark: string | null
  created_by: number | null
  updated_by: number | null
  created_at: string
  updated_at: string
}

export interface ArchiveBarcode {
  id: number
  code_type: "BARCODE" | "QRCODE"
  code_content: string
  image_path: string | null
  print_count: number
  last_printed_at: string | null
  created_by: number | null
  created_at: string
}

export interface ArchiveFile {
  id: number
  scan_task_item_id: number | null
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

export interface ArchiveFilePreviewTicket {
  access_url: string
  watermark_text: string
  expires_at: string
  file_name: string
  file_ext: string
}

export interface ArchiveFileDownloadTicket {
  access_url: string
  expires_at: string
  file_name: string
  purpose: string
}

export interface ArchiveMetadataRevision {
  id: number
  revision_no: number
  changed_fields_json: Record<string, { before: unknown; after: unknown }>
  snapshot_json: Record<string, unknown>
  remark: string | null
  revised_by: number
  revised_at: string
}

export interface ArchiveRecord {
  id: number
  archive_code: string
  title: string
  year: number
  retention_period: string
  security_level: string
  status: string
  responsible_dept_id: number | null
  responsible_dept_name: string | null
  responsible_person: string | null
  formed_at: string | null
  keywords: string | null
  summary: string | null
  page_count: number | null
  carrier_type: string | null
  location_id: number | null
  location_detail: ArchiveStorageLocation | null
  current_borrow_id: number | null
  catalog_completed_at: string | null
  shelved_at: string | null
  is_sensitive_masked: boolean
  masked_fields: string[]
  created_by: number | null
  updated_by: number | null
  created_at: string
  updated_at: string
}

export interface ArchiveRecordDetail extends ArchiveRecord {
  barcodes: ArchiveBarcode[]
  files: ArchiveFile[]
  revisions: ArchiveMetadataRevision[]
}

export interface ArchiveRecordPayload {
  archive_code: string
  title: string
  year: number
  retention_period: string
  security_level: string
  responsible_dept_id?: number | null
  responsible_person?: string
  formed_at?: string
  keywords?: string
  summary?: string
  page_count?: number | null
  carrier_type?: string
  location_id?: number | null
  revision_remark?: string
}

export interface ArchiveLocationPayload {
  warehouse_name: string
  area_name?: string
  cabinet_code: string
  rack_code: string
  layer_code: string
  box_code: string
  status: boolean
  remark?: string
}

export interface ArchiveStatusTransitionPayload {
  next_status: string
  current_borrow_id?: number
  remark?: string
}

export async function fetchArchiveLocations(params?: { search?: string }) {
  const response = await http.get<ApiResponse<ArchiveStorageLocation[]>>(
    "/archives/storage-locations/",
    { params },
  )
  return response.data
}

export async function fetchArchiveLocationsPage(params?: { search?: string } & PaginationQueryParams) {
  const response = await http.get<ApiResponse<PaginatedResponseData<ArchiveStorageLocation>>>(
    "/archives/storage-locations/",
    {
      params: {
        ...params,
        paginate: true,
      },
    },
  )
  return response.data
}

export async function createArchiveLocation(payload: ArchiveLocationPayload) {
  const response = await http.post<ApiResponse<ArchiveStorageLocation>>(
    "/archives/storage-locations/",
    payload,
  )
  return response.data
}

export async function updateArchiveLocation(locationId: number, payload: ArchiveLocationPayload) {
  const response = await http.put<ApiResponse<ArchiveStorageLocation>>(
    `/archives/storage-locations/${locationId}/`,
    payload,
  )
  return response.data
}

export interface ArchiveQueryParams {
  keyword?: string
  archive_code?: string
  year?: number
  retention_period?: string
  security_level?: string
  status?: string
  responsible_dept_id?: number
  location_id?: number
}

export async function fetchArchives(params?: ArchiveQueryParams) {
  const response = await http.get<ApiResponse<ArchiveRecord[]>>("/archives/records/", { params })
  return response.data
}

export async function fetchArchivesPage(params?: ArchiveQueryParams & PaginationQueryParams) {
  const response = await http.get<ApiResponse<PaginatedResponseData<ArchiveRecord>>>("/archives/records/", {
    params: {
      ...params,
      paginate: true,
    },
  })
  return response.data
}

export async function fetchArchiveDetail(archiveId: number) {
  const response = await http.get<ApiResponse<ArchiveRecordDetail>>(`/archives/records/${archiveId}/`)
  return response.data
}

export async function createArchiveRecord(payload: ArchiveRecordPayload) {
  const response = await http.post<ApiResponse<ArchiveRecordDetail>>("/archives/records/", payload)
  return response.data
}

export async function updateArchiveRecord(archiveId: number, payload: ArchiveRecordPayload) {
  const response = await http.put<ApiResponse<ArchiveRecordDetail>>(`/archives/records/${archiveId}/`, payload)
  return response.data
}

export async function generateArchiveCodes(archiveId: number) {
  const response = await http.post<ApiResponse<ArchiveRecordDetail>>(
    `/archives/records/${archiveId}/generate-codes/`,
  )
  return response.data
}

export async function printArchiveCodes(archiveId: number) {
  const response = await http.post<ApiResponse<ArchiveRecordDetail>>(
    `/archives/records/${archiveId}/print-codes/`,
  )
  return response.data
}

export async function batchPrintArchiveCodes(archiveIds: number[]) {
  const response = await http.post<ApiResponse<ArchiveRecordDetail[]>>(
    "/archives/records/batch-print-codes/",
    {
      archive_ids: archiveIds,
    },
  )
  return response.data
}

export async function createArchiveFilePreviewTicket(fileId: number) {
  const response = await http.post<ApiResponse<ArchiveFilePreviewTicket>>(
    `/archives/files/${fileId}/preview-ticket/`,
  )
  return response.data
}

export async function createArchiveFileDownloadTicket(fileId: number, payload: { purpose: string }) {
  const response = await http.post<ApiResponse<ArchiveFileDownloadTicket>>(
    `/archives/files/${fileId}/download-ticket/`,
    payload,
  )
  return response.data
}

export async function transitionArchiveStatus(
  archiveId: number,
  payload: ArchiveStatusTransitionPayload,
) {
  const response = await http.post<ApiResponse<ArchiveRecordDetail>>(
    `/archives/records/${archiveId}/transition-status/`,
    payload,
  )
  return response.data
}

export function buildArchiveAssetUrl(imagePath: string | null) {
  if (!imagePath) {
    return ""
  }
  return buildServerAssetUrl(`/media/${imagePath}`)
}

export function buildArchiveAccessUrl(accessUrl: string) {
  return buildServerAssetUrl(accessUrl)
}
