import { createRouter, createWebHistory, type RouteLocationNormalized } from "vue-router"

import { readStoredProfile } from "@/utils/session"
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
  profileHasAccess,
} from "@/utils/access"

const ROUTE_ACCESS_NOTICE_KEY = "asd_system_route_access_notice"

const ACCESS_TOKEN_KEY = "asd_system_access_token"

interface StoredProfile {
  roles: Array<{
    role_code: string
  }>
  permissions: Array<{
    permission_code: string
  }>
}

function storeRouteAccessNotice(message: string) {
  window.sessionStorage.setItem(ROUTE_ACCESS_NOTICE_KEY, message)
}

function getRoutePermissionCodes(to: RouteLocationNormalized) {
  const matchedRecord = [...to.matched]
    .reverse()
    .find((record) => Array.isArray(record.meta.permissionCodes) && record.meta.permissionCodes.length)
  return (matchedRecord?.meta.permissionCodes as string[] | undefined) || []
}

function getRouteFallbackRoles(to: RouteLocationNormalized) {
  const matchedRecord = [...to.matched]
    .reverse()
    .find((record) => Array.isArray(record.meta.fallbackRoles) && record.meta.fallbackRoles.length)
  return (matchedRecord?.meta.fallbackRoles as string[] | undefined) || []
}

function userCanAccessRoute(permissionCodes: readonly string[], fallbackRoles: readonly string[]) {
  const profile = readStoredProfile<StoredProfile>()
  if (!profile) {
    return false
  }
  return profileHasAccess(profile, { permissionCodes, fallbackRoles })
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("@/views/login/LoginView.vue"),
      meta: {
        title: "登录",
        description: "通过统一身份入口登录系统，并进入档案业务工作台。",
      },
    },
    {
      path: "/archives/records/print",
      name: "archive-record-print",
      component: () => import("@/views/archives/ArchivePrintView.vue"),
      meta: {
        title: "档案标签打印",
        description: "按选中的档案生成打印版面，并统一写入打印留痕。",
        permissionCodes: ["button.archive.print"],
        fallbackRoles: ARCHIVE_MANAGER_FALLBACK_ROLES,
      },
    },
    {
      path: "/",
      component: () => import("@/layouts/AppLayout.vue"),
      children: [
        {
          path: "",
          name: "dashboard",
          component: () => import("@/views/dashboard/DashboardView.vue"),
          meta: {
            title: "工作台",
            description: "查看待办、统计概览、快捷入口和业务提醒。",
            permissionCodes: ["menu.dashboard"],
            fallbackRoles: ALL_FALLBACK_ROLES,
          },
        },
        {
          path: "archives/records",
          name: "archive-record-list",
          component: () => import("@/views/archives/ArchiveListView.vue"),
          meta: {
            title: "档案中心",
            description: "检索档案，并从详情继续编辑、流转、打印和文件访问。",
            permissionCodes: ["menu.archive_center"],
            fallbackRoles: ARCHIVE_CENTER_FALLBACK_ROLES,
          },
        },
        {
          path: "archives/records/create",
          name: "archive-record-create",
          component: () => import("@/views/archives/ArchiveCreateView.vue"),
          meta: {
            title: "新建档案",
            description: "录入档号、题名、年度、保管期限、密级及基础编目信息。",
            permissionCodes: ["button.archive.create"],
            fallbackRoles: ARCHIVE_MANAGER_FALLBACK_ROLES,
          },
        },
        {
          path: "archives/records/:archiveId/edit",
          name: "archive-record-edit",
          component: () => import("@/views/archives/ArchiveCreateView.vue"),
          meta: {
            title: "编辑档案",
            description: "更新档案主数据，并自动写入修订记录。",
            permissionCodes: ["button.archive.edit"],
            fallbackRoles: ARCHIVE_MANAGER_FALLBACK_ROLES,
          },
        },
        {
          path: "archives/locations",
          name: "archive-location-list",
          component: () => import("@/views/archives/ArchiveLocationListView.vue"),
          meta: {
            title: "实体位置",
            description: "维护库房、区、柜、架、层、盒的标准化实体定位信息。",
            permissionCodes: ["menu.archive_location"],
            fallbackRoles: ARCHIVE_MANAGER_FALLBACK_ROLES,
          },
        },
        {
          path: "digitization/scan-tasks",
          name: "scan-task-list",
          component: () => import("@/views/digitization/ScanTaskListView.vue"),
          meta: {
            title: "扫描任务",
            description: "管理扫描任务、任务明细、执行人分配和数字化进度。",
            permissionCodes: ["menu.scan_task"],
            fallbackRoles: ARCHIVE_MANAGER_FALLBACK_ROLES,
          },
        },
        {
          path: "digitization/scan-tasks/:taskId",
          name: "scan-task-detail",
          component: () => import("@/views/digitization/ScanTaskDetailView.vue"),
          meta: {
            title: "任务详情",
            description: "上传 PDF 或图片文件，生成缩略图并完成档案绑定。",
            permissionCodes: ["menu.scan_task"],
            fallbackRoles: ARCHIVE_MANAGER_FALLBACK_ROLES,
          },
        },
        {
          path: "borrowing/applications",
          name: "borrow-application-list",
          component: () => import("@/views/borrowing/BorrowApplicationListView.vue"),
          meta: {
            title: "借阅中心",
            description: "提交借阅申请，并查看本人或授权范围内的借阅流转记录。",
            permissionCodes: ["menu.borrow_center"],
            fallbackRoles: BORROW_CENTER_FALLBACK_ROLES,
          },
        },
        {
          path: "borrowing/approvals",
          name: "borrow-approval-list",
          component: () => import("@/views/borrowing/BorrowApprovalView.vue"),
          meta: {
            title: "借阅审批",
            description: "处理当前用户待审批的借阅申请，并填写审批意见。",
            permissionCodes: ["menu.borrow_approval"],
            fallbackRoles: SYSTEM_MANAGER_FALLBACK_ROLES,
          },
        },
        {
          path: "borrowing/checkout",
          name: "borrow-checkout-list",
          component: () => import("@/views/borrowing/BorrowCheckoutView.vue"),
          meta: {
            title: "出库登记",
            description: "对审批通过的借阅申请办理实体档案出库登记。",
            permissionCodes: ["menu.borrow_checkout"],
            fallbackRoles: ARCHIVE_MANAGER_FALLBACK_ROLES,
          },
        },
        {
          path: "borrowing/returns",
          name: "borrow-return-list",
          component: () => import("@/views/borrowing/BorrowReturnView.vue"),
          meta: {
            title: "归还中心",
            description: "提交归还凭证，并处理档案员归还验收与重新入库。",
            permissionCodes: ["menu.borrow_return"],
            fallbackRoles: BORROW_RETURN_FALLBACK_ROLES,
          },
        },
        {
          path: "notifications/messages",
          name: "notification-center",
          component: () => import("@/views/notifications/NotificationCenterView.vue"),
          meta: {
            title: "通知中心",
            description: "查看借阅催还、审批流转和系统消息，并执行已读处理。",
            permissionCodes: ["menu.notification_center"],
            fallbackRoles: NOTIFICATION_FALLBACK_ROLES,
          },
        },
        {
          path: "destruction/applications",
          name: "destruction-center",
          component: () => import("@/views/destruction/DestructionCenterView.vue"),
          meta: {
            title: "销毁中心",
            description: "处理档案销毁申请、管理员审批、执行登记与附件留痕。",
            permissionCodes: ["menu.destruction_center"],
            fallbackRoles: DESTRUCTION_VIEW_FALLBACK_ROLES,
          },
        },
        {
          path: "audit/logs",
          name: "audit-log",
          component: () => import("@/views/audit/AuditLogView.vue"),
          meta: {
            title: "审计日志",
            description: "查看关键业务操作留痕、异常结果和文件访问风控记录。",
            permissionCodes: ["menu.audit_log"],
            fallbackRoles: AUDIT_VIEW_FALLBACK_ROLES,
          },
        },
        {
          path: "reports/center",
          name: "report-center",
          component: () => import("@/views/reports/ReportCenterView.vue"),
          meta: {
            title: "报表中心",
            description: "查看借阅汇总、部门排行、档案利用率并导出统计报表。",
            permissionCodes: ["menu.report_center"],
            fallbackRoles: REPORT_VIEW_FALLBACK_ROLES,
          },
        },
        {
          path: "system/management",
          name: "system-management",
          component: () => import("@/views/system/SystemManagementView.vue"),
          meta: {
            title: "系统管理",
            description: "集中维护用户、角色、组织架构与后端健康状态。",
            permissionCodes: ["menu.system_management"],
            fallbackRoles: SYSTEM_MANAGER_FALLBACK_ROLES,
          },
        },
      ],
    },
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: () => import("@/views/not-found/NotFoundView.vue"),
      meta: {
        title: "页面不存在",
      },
    },
  ],
})

router.beforeEach((to) => {
  const token = window.localStorage.getItem(ACCESS_TOKEN_KEY)
  if (to.name !== "login" && !token) {
    return {
      name: "login",
      query: {
        redirect: to.fullPath,
      },
    }
  }

  if (to.name === "login" && token) {
    return { name: "dashboard" }
  }

  const permissionCodes = getRoutePermissionCodes(to)
  const fallbackRoles = getRouteFallbackRoles(to)
  if (token && permissionCodes.length && !userCanAccessRoute(permissionCodes, fallbackRoles)) {
    storeRouteAccessNotice(`当前账号无权访问“${String(to.meta.title || "目标页面")}”，已为你返回工作台。`)
    return { name: "dashboard" }
  }

  return true
})

router.afterEach((to) => {
  const appTitle = import.meta.env.VITE_APP_TITLE || "岚仓档案数字化与流转系统"
  document.title = to.meta.title ? `${String(to.meta.title)} - ${appTitle}` : appTitle
})

export default router
