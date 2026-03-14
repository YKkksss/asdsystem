import http, { type ApiResponse } from "@/api/http"


export interface SystemNotification {
  id: number
  notification_type: string
  title: string
  content: string
  biz_type: string | null
  biz_id: number | null
  is_read: boolean
  read_at: string | null
  created_at: string
  updated_at: string
}

export interface NotificationSummary {
  total_count: number
  unread_count: number
  reminder_unread_count: number
}

export interface NotificationQueryParams {
  notification_type?: string
  is_read?: boolean
}

export async function fetchNotifications(params?: NotificationQueryParams) {
  const response = await http.get<ApiResponse<SystemNotification[]>>("/notifications/messages/", { params })
  return response.data
}

export async function fetchNotificationSummary() {
  const response = await http.get<ApiResponse<NotificationSummary>>("/notifications/summary/")
  return response.data
}

export async function markNotificationAsRead(notificationId: number) {
  const response = await http.post<ApiResponse<SystemNotification>>(
    `/notifications/messages/${notificationId}/mark-read/`,
  )
  return response.data
}

export async function markAllNotificationsAsRead() {
  const response = await http.post<ApiResponse<{ updated_count: number }>>(
    "/notifications/messages/mark-all-read/",
  )
  return response.data
}
