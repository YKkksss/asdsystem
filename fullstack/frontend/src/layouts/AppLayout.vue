<template>
  <div class="layout-shell">
    <aside class="layout-sidebar">
      <div class="brand-block">
        <p class="brand-tag">{{ appStore.stageTitle }}</p>
        <h1>{{ appStore.appTitle }}</h1>
        <p class="brand-text">围绕档案全生命周期管理构建统一工作台。</p>
      </div>

      <nav class="menu-list">
        <RouterLink
          v-for="item in menuItems"
          :key="item.path"
          class="menu-item"
          :to="item.path"
        >
          <span>{{ item.name }}</span>
          <small>{{ item.caption }}</small>
        </RouterLink>
      </nav>
    </aside>

    <main class="layout-main">
      <header class="topbar">
        <div>
          <strong>{{ currentTitle }}</strong>
          <p>{{ currentDescription }}</p>
        </div>

        <div class="action-group">
          <div v-if="authStore.profile" class="user-card">
            <strong>{{ authStore.profile.real_name }}</strong>
            <span>{{ authStore.profile.dept_name }}</span>
          </div>

          <a-button
            v-if="authStore.isAuthenticated"
            class="login-link"
            type="primary"
            :loading="logoutSubmitting"
            @click="handleLogout"
          >
            退出登录
          </a-button>
          <RouterLink v-else class="login-link" to="/login">查看登录页</RouterLink>
        </div>
      </header>

      <section class="content-panel">
        <RouterView />
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"
import { message } from "ant-design-vue"
import { RouterLink, RouterView } from "vue-router"
import { useRoute, useRouter } from "vue-router"

import { logout } from "@/api/auth"
import { useAppStore } from "@/stores/app"
import { useAuthStore } from "@/stores/auth"

const appStore = useAppStore()
const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const logoutSubmitting = ref(false)
const ROUTE_ACCESS_NOTICE_KEY = "asd_system_route_access_notice"

const canManageArchives = computed(() =>
  Boolean(authStore.profile?.roles.some((role) => ["ADMIN", "ARCHIVIST"].includes(role.role_code))),
)

const canViewAudit = computed(() =>
  Boolean(authStore.profile?.roles.some((role) => ["ADMIN", "AUDITOR"].includes(role.role_code))),
)

const canViewReports = computed(() =>
  Boolean(authStore.profile?.roles.some((role) => ["ADMIN", "AUDITOR", "ARCHIVIST"].includes(role.role_code))),
)

const canViewDestruction = computed(() =>
  Boolean(authStore.profile?.roles.some((role) => ["ADMIN", "AUDITOR", "ARCHIVIST"].includes(role.role_code))),
)

const canManageSystem = computed(() =>
  Boolean(authStore.profile?.roles.some((role) => role.role_code === "ADMIN")),
)

const menuItems = computed(() => {
  const items = [
    { path: "/", name: "工作台", caption: "查看当前交付阶段" },
    { path: "/archives/records", name: "档案检索", caption: "按组合条件检索并查看脱敏结果" },
    { path: "/borrowing/applications", name: "借阅申请", caption: "发起借阅并查看流转记录" },
    { path: "/borrowing/approvals", name: "借阅审批", caption: "处理当前待审批借阅申请" },
    { path: "/borrowing/returns", name: "归还中心", caption: "提交归还并处理验收入库" },
    { path: "/notifications/messages", name: "通知中心", caption: "查看催还提醒和系统消息" },
  ]

  if (canManageArchives.value) {
    items.push(
      { path: "/archives/records/create", name: "新建档案", caption: "录入入库主数据" },
      { path: "/archives/locations", name: "实体位置", caption: "维护库房柜架盒位" },
      { path: "/digitization/scan-tasks", name: "扫描任务", caption: "分配任务并上传扫描文件" },
      { path: "/borrowing/checkout", name: "出库登记", caption: "办理审批通过档案的出库" },
    )
  }

  if (canViewDestruction.value) {
    items.push(
      { path: "/destruction/applications", name: "销毁中心", caption: "查看销毁流转并登记执行结果" },
    )
  }

  if (canViewReports.value) {
    items.push(
      { path: "/reports/center", name: "报表中心", caption: "查看借阅统计并导出汇总报表" },
    )
  }

  if (canViewAudit.value) {
    items.push(
      { path: "/audit/logs", name: "审计日志", caption: "查看关键操作留痕和文件访问风控记录" },
    )
  }

  if (canManageSystem.value) {
    items.push(
      { path: "/system/management", name: "系统管理", caption: "维护用户、角色、组织与运行状态" },
    )
  }

  return items
})

const currentTitle = computed(() => String(route.meta.title || appStore.titleWithStage))
const currentDescription = computed(() => String(route.meta.description || appStore.pageDescription))

function consumeRouteAccessNotice() {
  const notice = window.sessionStorage.getItem(ROUTE_ACCESS_NOTICE_KEY)
  if (!notice) {
    return
  }
  window.sessionStorage.removeItem(ROUTE_ACCESS_NOTICE_KEY)
  message.warning(notice)
}

async function handleLogout() {
  logoutSubmitting.value = true
  try {
    const response = await logout()
    message.success(response.message)
  } catch (error) {
    const response = error as { response?: { data?: { message?: string } } }
    message.warning(response?.response?.data?.message || "退出登录请求失败，已清理本地登录状态。")
  } finally {
    authStore.clearSession()
    logoutSubmitting.value = false
    await router.push("/login")
  }
}

watch(
  () => route.fullPath,
  () => {
    consumeRouteAccessNotice()
  },
  { immediate: true },
)
</script>

<style scoped>
.layout-shell {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  height: 100vh;
  overflow: hidden;
}

.layout-sidebar {
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 28px 24px;
  background:
    linear-gradient(180deg, rgba(10, 113, 82, 0.96) 0%, rgba(23, 84, 70, 0.94) 100%),
    #0a7152;
  color: #f8fffc;
}

.brand-block h1 {
  margin: 0;
  font-size: 28px;
}

.brand-tag {
  width: fit-content;
  margin: 0 0 12px;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
  font-size: 12px;
  letter-spacing: 0.08em;
}

.brand-text {
  margin: 12px 0 0;
  color: rgba(248, 255, 252, 0.78);
  line-height: 1.7;
}

.menu-list {
  display: grid;
  flex: 1;
  min-height: 0;
  gap: 12px;
  margin-top: 32px;
  overflow-y: auto;
  padding-right: 6px;
  align-content: start;
  scrollbar-gutter: stable;
}

.menu-list::-webkit-scrollbar {
  width: 6px;
}

.menu-list::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.26);
}

.menu-list::-webkit-scrollbar-track {
  background: transparent;
}

.menu-item {
  display: grid;
  gap: 4px;
  padding: 14px 16px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.06);
  transition: transform 0.2s ease, background-color 0.2s ease;
}

.menu-item:hover {
  transform: translateX(3px);
  background: rgba(255, 255, 255, 0.1);
}

.menu-item.router-link-active {
  border-color: rgba(255, 255, 255, 0.32);
  background: rgba(255, 255, 255, 0.16);
}

.menu-item small {
  color: rgba(248, 255, 252, 0.7);
}

.layout-main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  box-sizing: border-box;
  height: 100vh;
  padding: 24px;
}

.topbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 20px;
}

.topbar strong {
  font-size: 18px;
}

.topbar p {
  margin: 8px 0 0;
  color: #475467;
}

.action-group {
  display: flex;
  gap: 12px;
  align-items: center;
}

.user-card {
  display: grid;
  gap: 4px;
  padding: 10px 14px;
  border-radius: 16px;
  background: rgba(10, 113, 82, 0.08);
}

.user-card span {
  color: #475467;
  font-size: 12px;
}

.login-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 40px;
  padding: 0 18px;
  border-radius: 999px;
  background: #0a7152;
  color: #ffffff;
  line-height: 1;
  white-space: nowrap;
}

.login-link :deep(span) {
  display: inline-flex;
  align-items: center;
}

.content-panel {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 24px;
  border: 1px solid rgba(10, 113, 82, 0.12);
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 20px 60px rgba(14, 53, 42, 0.08);
  backdrop-filter: blur(18px);
}

@media (max-width: 960px) {
  .layout-shell {
    grid-template-columns: 1fr;
    height: auto;
    overflow: visible;
  }

  .layout-main {
    height: auto;
    overflow: visible;
    padding: 16px;
  }

  .content-panel {
    overflow: visible;
    min-height: auto;
  }

  .topbar {
    flex-direction: column;
  }

  .action-group {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
