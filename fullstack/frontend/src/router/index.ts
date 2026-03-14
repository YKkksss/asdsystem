import { createRouter, createWebHistory, type RouteLocationNormalized } from "vue-router"

import { readStoredProfile } from "@/utils/session"

const ROUTE_ACCESS_NOTICE_KEY = "asd_system_route_access_notice"

const ACCESS_TOKEN_KEY = "asd_system_access_token"
const MANAGE_ARCHIVE_ROLE_CODES = ["ADMIN", "ARCHIVIST"] as const
const REPORT_VIEW_ROLE_CODES = ["ADMIN", "AUDITOR", "ARCHIVIST"] as const
const AUDIT_VIEW_ROLE_CODES = ["ADMIN", "AUDITOR"] as const
const SYSTEM_MANAGE_ROLE_CODES = ["ADMIN"] as const

type RoleCode = typeof MANAGE_ARCHIVE_ROLE_CODES[number] | typeof REPORT_VIEW_ROLE_CODES[number]

interface StoredProfile {
  roles: Array<{
    role_code: string
  }>
}

function storeRouteAccessNotice(message: string) {
  window.sessionStorage.setItem(ROUTE_ACCESS_NOTICE_KEY, message)
}

function getRouteRequiredRoles(to: RouteLocationNormalized) {
  const matchedRecord = [...to.matched]
    .reverse()
    .find((record) => Array.isArray(record.meta.allowedRoles) && record.meta.allowedRoles.length)
  return (matchedRecord?.meta.allowedRoles as RoleCode[] | undefined) || []
}

function userHasAnyRequiredRole(requiredRoles: readonly string[]) {
  if (!requiredRoles.length) {
    return true
  }

  const profile = readStoredProfile<StoredProfile>()
  if (!profile) {
    return true
  }

  return profile.roles.some((role) => requiredRoles.includes(role.role_code))
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
        allowedRoles: [...MANAGE_ARCHIVE_ROLE_CODES],
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
            description: "查看当前已交付模块、开发阶段和后续业务推进顺序。",
          },
        },
        {
          path: "archives/records",
          name: "archive-record-list",
          component: () => import("@/views/archives/ArchiveListView.vue"),
          meta: {
            title: "档案检索",
            description: "按关键词与多字段组合检索档案，并查看脱敏后的详情结果。",
          },
        },
        {
          path: "archives/records/create",
          name: "archive-record-create",
          component: () => import("@/views/archives/ArchiveCreateView.vue"),
          meta: {
            title: "新建档案",
            description: "录入档号、题名、年度、保管期限、密级及基础编目信息。",
            allowedRoles: [...MANAGE_ARCHIVE_ROLE_CODES],
          },
        },
        {
          path: "archives/records/:archiveId/edit",
          name: "archive-record-edit",
          component: () => import("@/views/archives/ArchiveCreateView.vue"),
          meta: {
            title: "编辑档案",
            description: "更新档案主数据，并自动写入修订记录。",
            allowedRoles: [...MANAGE_ARCHIVE_ROLE_CODES],
          },
        },
        {
          path: "archives/locations",
          name: "archive-location-list",
          component: () => import("@/views/archives/ArchiveLocationListView.vue"),
          meta: {
            title: "实体位置",
            description: "维护库房、区、柜、架、层、盒的标准化实体定位信息。",
            allowedRoles: [...MANAGE_ARCHIVE_ROLE_CODES],
          },
        },
        {
          path: "digitization/scan-tasks",
          name: "scan-task-list",
          component: () => import("@/views/digitization/ScanTaskListView.vue"),
          meta: {
            title: "扫描任务",
            description: "管理扫描任务、任务明细、执行人分配和数字化进度。",
            allowedRoles: [...MANAGE_ARCHIVE_ROLE_CODES],
          },
        },
        {
          path: "digitization/scan-tasks/:taskId",
          name: "scan-task-detail",
          component: () => import("@/views/digitization/ScanTaskDetailView.vue"),
          meta: {
            title: "任务详情",
            description: "上传 PDF 或图片文件，生成缩略图并完成档案绑定。",
            allowedRoles: [...MANAGE_ARCHIVE_ROLE_CODES],
          },
        },
        {
          path: "borrowing/applications",
          name: "borrow-application-list",
          component: () => import("@/views/borrowing/BorrowApplicationListView.vue"),
          meta: {
            title: "借阅申请",
            description: "提交借阅申请，并查看本人或授权范围内的借阅流转记录。",
          },
        },
        {
          path: "borrowing/approvals",
          name: "borrow-approval-list",
          component: () => import("@/views/borrowing/BorrowApprovalView.vue"),
          meta: {
            title: "借阅审批",
            description: "处理当前用户待审批的借阅申请，并填写审批意见。",
          },
        },
        {
          path: "borrowing/checkout",
          name: "borrow-checkout-list",
          component: () => import("@/views/borrowing/BorrowCheckoutView.vue"),
          meta: {
            title: "出库登记",
            description: "对审批通过的借阅申请办理实体档案出库登记。",
            allowedRoles: [...MANAGE_ARCHIVE_ROLE_CODES],
          },
        },
        {
          path: "borrowing/returns",
          name: "borrow-return-list",
          component: () => import("@/views/borrowing/BorrowReturnView.vue"),
          meta: {
            title: "归还中心",
            description: "提交归还凭证，并处理档案员归还验收与重新入库。",
          },
        },
        {
          path: "notifications/messages",
          name: "notification-center",
          component: () => import("@/views/notifications/NotificationCenterView.vue"),
          meta: {
            title: "通知中心",
            description: "查看借阅催还、审批流转和系统消息，并执行已读处理。",
          },
        },
        {
          path: "destruction/applications",
          name: "destruction-center",
          component: () => import("@/views/destruction/DestructionCenterView.vue"),
          meta: {
            title: "销毁中心",
            description: "处理档案销毁申请、管理员审批、执行登记与附件留痕。",
            allowedRoles: [...REPORT_VIEW_ROLE_CODES],
          },
        },
        {
          path: "audit/logs",
          name: "audit-log",
          component: () => import("@/views/audit/AuditLogView.vue"),
          meta: {
            title: "审计日志",
            description: "查看关键业务操作留痕、异常结果和文件访问风控记录。",
            allowedRoles: [...AUDIT_VIEW_ROLE_CODES],
          },
        },
        {
          path: "reports/center",
          name: "report-center",
          component: () => import("@/views/reports/ReportCenterView.vue"),
          meta: {
            title: "报表中心",
            description: "查看借阅汇总、部门排行、档案利用率并导出统计报表。",
            allowedRoles: [...REPORT_VIEW_ROLE_CODES],
          },
        },
        {
          path: "system/management",
          name: "system-management",
          component: () => import("@/views/system/SystemManagementView.vue"),
          meta: {
            title: "系统管理",
            description: "集中维护用户、角色、组织架构与后端健康状态。",
            allowedRoles: [...SYSTEM_MANAGE_ROLE_CODES],
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

  const requiredRoles = getRouteRequiredRoles(to)
  if (token && requiredRoles.length && !userHasAnyRequiredRole(requiredRoles)) {
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
