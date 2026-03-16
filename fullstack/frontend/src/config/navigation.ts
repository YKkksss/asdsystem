import {
  ALL_FALLBACK_ROLES,
  ARCHIVE_CENTER_FALLBACK_ROLES,
  ARCHIVE_MANAGER_FALLBACK_ROLES,
  AUDIT_VIEW_FALLBACK_ROLES,
  BORROW_CENTER_FALLBACK_ROLES,
  BORROW_RETURN_FALLBACK_ROLES,
  DESTRUCTION_VIEW_FALLBACK_ROLES,
  NOTIFICATION_FALLBACK_ROLES,
  REPORT_VIEW_FALLBACK_ROLES,
  SYSTEM_MANAGER_FALLBACK_ROLES,
  type AccessRule,
} from "@/utils/access"

export interface NavigationItem extends AccessRule {
  kind: "item"
  key: string
  path: string
  name: string
  caption: string
  activePrefixes: string[]
  quickAction?: boolean
}

export interface NavigationGroup {
  kind: "group"
  key: string
  title: string
  items: NavigationItem[]
}

export type NavigationEntry = NavigationItem | NavigationGroup

export const navigationEntries: NavigationEntry[] = [
  {
    kind: "item",
    key: "dashboard",
    path: "/",
    name: "工作台",
    caption: "查看待办、统计和快捷入口",
    permissionCodes: ["menu.dashboard"],
    fallbackRoles: ALL_FALLBACK_ROLES,
    activePrefixes: ["/"],
    quickAction: true,
  },
  {
    kind: "group",
    key: "archives",
    title: "档案业务",
    items: [
      {
        kind: "item",
        key: "archive-center",
        path: "/archives/records",
        name: "档案中心",
        caption: "检索档案并从详情继续编辑、流转和打印",
        permissionCodes: ["menu.archive_center"],
        fallbackRoles: ARCHIVE_CENTER_FALLBACK_ROLES,
        activePrefixes: ["/archives/records"],
        quickAction: true,
      },
      {
        kind: "item",
        key: "archive-location",
        path: "/archives/locations",
        name: "实体位置",
        caption: "维护库房、柜架、层盒与位置标准编码",
        permissionCodes: ["menu.archive_location"],
        fallbackRoles: ARCHIVE_MANAGER_FALLBACK_ROLES,
        activePrefixes: ["/archives/locations"],
      },
      {
        kind: "item",
        key: "scan-task",
        path: "/digitization/scan-tasks",
        name: "数字化任务",
        caption: "安排扫描、上传文件并跟踪处理结果",
        permissionCodes: ["menu.scan_task"],
        fallbackRoles: ARCHIVE_MANAGER_FALLBACK_ROLES,
        activePrefixes: ["/digitization/scan-tasks"],
      },
      {
        kind: "item",
        key: "destruction-center",
        path: "/destruction/applications",
        name: "销毁中心",
        caption: "跟踪销毁申请、审批流转和执行留痕",
        permissionCodes: ["menu.destruction_center"],
        fallbackRoles: DESTRUCTION_VIEW_FALLBACK_ROLES,
        activePrefixes: ["/destruction/applications"],
      },
    ],
  },
  {
    kind: "group",
    key: "borrowing",
    title: "借阅业务",
    items: [
      {
        kind: "item",
        key: "borrow-center",
        path: "/borrowing/applications",
        name: "借阅中心",
        caption: "发起申请并查看本人或业务范围内的借阅记录",
        permissionCodes: ["menu.borrow_center"],
        fallbackRoles: BORROW_CENTER_FALLBACK_ROLES,
        activePrefixes: ["/borrowing/applications"],
        quickAction: true,
      },
      {
        kind: "item",
        key: "borrow-approval",
        path: "/borrowing/approvals",
        name: "借阅审批",
        caption: "处理当前指派给我的借阅审批任务",
        permissionCodes: ["menu.borrow_approval"],
        fallbackRoles: SYSTEM_MANAGER_FALLBACK_ROLES,
        activePrefixes: ["/borrowing/approvals"],
        quickAction: true,
      },
      {
        kind: "item",
        key: "borrow-checkout",
        path: "/borrowing/checkout",
        name: "出库登记",
        caption: "对审批通过的借阅单办理实体出库",
        permissionCodes: ["menu.borrow_checkout"],
        fallbackRoles: ARCHIVE_MANAGER_FALLBACK_ROLES,
        activePrefixes: ["/borrowing/checkout"],
      },
      {
        kind: "item",
        key: "borrow-return",
        path: "/borrowing/returns",
        name: "归还中心",
        caption: "借阅人提交归还，档案员处理验收入库",
        permissionCodes: ["menu.borrow_return"],
        fallbackRoles: BORROW_RETURN_FALLBACK_ROLES,
        activePrefixes: ["/borrowing/returns"],
        quickAction: true,
      },
      {
        kind: "item",
        key: "notification-center",
        path: "/notifications/messages",
        name: "通知中心",
        caption: "集中查看审批、催还、归还和系统消息",
        permissionCodes: ["menu.notification_center"],
        fallbackRoles: NOTIFICATION_FALLBACK_ROLES,
        activePrefixes: ["/notifications/messages"],
        quickAction: true,
      },
    ],
  },
  {
    kind: "group",
    key: "insight",
    title: "统计监督",
    items: [
      {
        kind: "item",
        key: "report-center",
        path: "/reports/center",
        name: "报表中心",
        caption: "查看借阅汇总、部门排行与利用率统计",
        permissionCodes: ["menu.report_center"],
        fallbackRoles: REPORT_VIEW_FALLBACK_ROLES,
        activePrefixes: ["/reports/center"],
      },
      {
        kind: "item",
        key: "audit-log",
        path: "/audit/logs",
        name: "审计日志",
        caption: "查看关键操作留痕与文件访问风控记录",
        permissionCodes: ["menu.audit_log"],
        fallbackRoles: AUDIT_VIEW_FALLBACK_ROLES,
        activePrefixes: ["/audit/logs"],
      },
    ],
  },
  {
    kind: "group",
    key: "system",
    title: "系统管理",
    items: [
      {
        kind: "item",
        key: "system-management",
        path: "/system/management",
        name: "系统管理",
        caption: "统一管理账号、角色、权限和运行状态",
        permissionCodes: ["menu.system_management"],
        fallbackRoles: SYSTEM_MANAGER_FALLBACK_ROLES,
        activePrefixes: ["/system/management"],
        quickAction: true,
      },
    ],
  },
]

export const dashboardQuickActionKeys = [
  "archive-center",
  "scan-task",
  "borrow-center",
  "borrow-approval",
  "borrow-return",
  "notification-center",
  "report-center",
  "audit-log",
  "system-management",
] as const

export function flattenNavigationItems(entries: NavigationEntry[]) {
  return entries.flatMap((entry) => (entry.kind === "item" ? [entry] : entry.items))
}
