import http, { type ApiResponse } from "@/api/http"


export interface SystemHealthPayload {
  service: string
  status: string
  time: string
  version: string
}

export interface SystemDashboardCard {
  key: string
  label: string
  value: number
  caption: string
  tone: string
  route_path: string | null
}

export interface SystemDashboardSection {
  key: string
  title: string
  description: string
  items: SystemDashboardCard[]
}

export interface SystemDashboardListItem {
  key: string
  title: string
  description: string
  meta: string
  tone: string
  badge: string | null
  route_path: string | null
}

export interface SystemDashboardTrendItem {
  label: string
  value: number
  caption: string
  tone: string
}

export interface SystemDashboardTrendSection {
  key: string
  title: string
  description: string
  unit: string
  items: SystemDashboardTrendItem[]
}

export interface SystemDashboardPayload {
  headline: string
  subtitle: string
  priority_focus: SystemDashboardCard | null
  summary_cards: SystemDashboardCard[]
  todo_cards: SystemDashboardCard[]
  workflow_sections: SystemDashboardSection[]
  trend_sections: SystemDashboardTrendSection[]
  signal_cards: SystemDashboardCard[]
  pending_task_items: SystemDashboardListItem[]
  recent_notifications: SystemDashboardListItem[]
}

export async function fetchSystemHealth() {
  const response = await http.get<ApiResponse<SystemHealthPayload>>("/system/health/")
  return response.data
}

export async function fetchSystemDashboard() {
  const response = await http.get<ApiResponse<SystemDashboardPayload>>("/system/dashboard/")
  return response.data
}
