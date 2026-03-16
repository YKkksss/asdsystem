<template>
  <div class="layout-shell">
    <aside class="layout-sidebar">
      <div class="brand-block">
        <p class="brand-tag">{{ appStore.stageTitle }}</p>
        <h1>{{ appStore.appTitle }}</h1>
        <p class="brand-text">统一承接档案、借阅、归还、销毁与监督业务入口。</p>
      </div>

      <nav class="menu-list">
        <a-menu
          class="sidebar-menu"
          mode="inline"
          :open-keys="openMenuKeys"
          :selected-keys="selectedMenuKeys"
          @openChange="handleOpenChange"
        >
          <template v-for="entry in accessibleNavigationEntries" :key="entry.key">
            <a-menu-item v-if="entry.kind === 'item'" :key="entry.key">
              <RouterLink :to="entry.path">{{ entry.name }}</RouterLink>
            </a-menu-item>

            <a-sub-menu v-else :key="entry.key">
              <template #title>{{ entry.title }}</template>

              <a-menu-item v-for="item in entry.items" :key="item.key">
                <RouterLink :to="item.path">{{ item.name }}</RouterLink>
              </a-menu-item>
            </a-sub-menu>
          </template>
        </a-menu>
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
          <RouterLink v-else class="login-link login-link-text" to="/login">查看登录页</RouterLink>
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
import { flattenNavigationItems, navigationEntries, type NavigationEntry, type NavigationItem } from "@/config/navigation"
import { useAppStore } from "@/stores/app"
import { useAuthStore } from "@/stores/auth"
import { profileHasAccess } from "@/utils/access"

const appStore = useAppStore()
const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const logoutSubmitting = ref(false)
const openMenuKeys = ref<string[]>([])
const ROUTE_ACCESS_NOTICE_KEY = "asd_system_route_access_notice"

const accessibleNavigationEntries = computed<NavigationEntry[]>(() =>
  navigationEntries
    .map((entry) => {
      if (entry.kind === "item") {
        return profileHasAccess(authStore.profile, entry) ? entry : null
      }

      const visibleItems = entry.items.filter((item) => profileHasAccess(authStore.profile, item))
      if (!visibleItems.length) {
        return null
      }
      return {
        ...entry,
        items: visibleItems,
      }
    })
    .filter((entry): entry is NavigationEntry => Boolean(entry)),
)

const accessibleNavigationItems = computed(() => flattenNavigationItems(accessibleNavigationEntries.value))
const accessibleGroupKeys = computed(() =>
  accessibleNavigationEntries.value
    .filter((entry): entry is Extract<NavigationEntry, { kind: "group" }> => entry.kind === "group")
    .map((entry) => entry.key),
)

const currentTitle = computed(() => String(route.meta.title || appStore.titleWithStage))
const currentDescription = computed(() => String(route.meta.description || appStore.pageDescription))

const activeNavigationItem = computed(() => {
  let matchedItem: NavigationItem | null = null
  let matchedScore = -1

  for (const item of accessibleNavigationItems.value) {
    if (item.path === "/") {
      if (route.path === "/" && matchedScore < 1) {
        matchedItem = item
        matchedScore = 1
      }
      continue
    }

    const matchedPrefix = item.activePrefixes
      .filter((prefix) => route.path.startsWith(prefix))
      .sort((left, right) => right.length - left.length)[0]

    if (matchedPrefix && matchedPrefix.length > matchedScore) {
      matchedItem = item
      matchedScore = matchedPrefix.length
    }
  }

  return matchedItem
})

const activeParentKey = computed(() => {
  const currentItem = activeNavigationItem.value
  if (!currentItem) {
    return null
  }

  const parentEntry = accessibleNavigationEntries.value.find(
    (entry) => entry.kind === "group" && entry.items.some((item) => item.key === currentItem.key),
  )
  return parentEntry?.key || null
})

const selectedMenuKeys = computed(() => (activeNavigationItem.value ? [activeNavigationItem.value.key] : []))

function consumeRouteAccessNotice() {
  const notice = window.sessionStorage.getItem(ROUTE_ACCESS_NOTICE_KEY)
  if (!notice) {
    return
  }
  window.sessionStorage.removeItem(ROUTE_ACCESS_NOTICE_KEY)
  message.warning(notice)
}

function normalizeOpenMenuKeys(keys: string[]) {
  const visibleKeySet = new Set(accessibleGroupKeys.value)
  const normalizedKeys = keys.filter((key) => visibleKeySet.has(key))

  if (activeParentKey.value && !normalizedKeys.includes(activeParentKey.value)) {
    normalizedKeys.push(activeParentKey.value)
  }

  return normalizedKeys
}

function handleOpenChange(keys: string[]) {
  openMenuKeys.value = normalizeOpenMenuKeys(keys)
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
  [accessibleGroupKeys, activeParentKey],
  () => {
    openMenuKeys.value = normalizeOpenMenuKeys(openMenuKeys.value)
  },
  { immediate: true },
)

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
  grid-template-columns: 300px minmax(0, 1fr);
  height: 100vh;
  overflow: hidden;
}

.layout-sidebar {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: 28px 20px 24px;
  background:
    linear-gradient(180deg, rgba(10, 113, 82, 0.96) 0%, rgba(23, 84, 70, 0.94) 100%),
    #0a7152;
  color: #f8fffc;
}

.brand-block {
  display: grid;
  gap: 12px;
  padding: 0 4px;
}

.brand-block h1 {
  margin: 0;
  font-size: 28px;
}

.brand-tag {
  width: fit-content;
  margin: 0;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.14);
  font-size: 12px;
  letter-spacing: 0.08em;
}

.brand-text {
  margin: 0;
  color: rgba(248, 255, 252, 0.78);
  line-height: 1.7;
}

.menu-list {
  flex: 1;
  min-height: 0;
  margin-top: 28px;
  overflow-y: auto;
  padding-right: 4px;
  padding-bottom: 8px;
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

.sidebar-menu {
  background: transparent;
  color: rgba(248, 255, 252, 0.86);
}

.sidebar-menu :deep(.ant-menu) {
  background: transparent;
  border-inline-end: none;
  color: rgba(248, 255, 252, 0.86);
}

.sidebar-menu :deep(.ant-menu-sub.ant-menu-inline) {
  background: transparent;
}

.sidebar-menu :deep(.ant-menu-item),
.sidebar-menu :deep(.ant-menu-submenu-title) {
  height: 46px;
  margin: 6px 0;
  line-height: 46px;
  border-radius: 14px;
  color: rgba(248, 255, 252, 0.82);
  transition: background-color 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.sidebar-menu :deep(.ant-menu-item:hover),
.sidebar-menu :deep(.ant-menu-submenu-title:hover) {
  color: #91caff;
  background: rgba(255, 255, 255, 0.08);
}

.sidebar-menu :deep(.ant-menu-item:hover .ant-menu-title-content),
.sidebar-menu :deep(.ant-menu-item:hover .ant-menu-title-content a),
.sidebar-menu :deep(.ant-menu-submenu-title:hover .ant-menu-title-content) {
  color: #91caff;
}

.sidebar-menu :deep(.ant-menu-item-selected) {
  color: #ffffff;
  background: rgba(255, 255, 255, 0.16);
}

.sidebar-menu :deep(.ant-menu-submenu-selected > .ant-menu-submenu-title) {
  color: #ffffff;
}

.sidebar-menu :deep(.ant-menu-title-content) {
  font-weight: 500;
}

.sidebar-menu :deep(.ant-menu-title-content a) {
  display: block;
  width: 100%;
  color: inherit;
}

.sidebar-menu :deep(.ant-menu-title-content a:hover) {
  color: inherit;
}

.sidebar-menu :deep(.ant-menu-submenu-title .ant-menu-title-content) {
  letter-spacing: 0.02em;
}

.sidebar-menu :deep(.ant-menu-submenu-arrow),
.sidebar-menu :deep(.ant-menu-submenu-arrow::before),
.sidebar-menu :deep(.ant-menu-submenu-arrow::after) {
  color: rgba(248, 255, 252, 0.78);
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
  align-items: center;
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
  min-width: 108px;
  height: 40px;
  padding: 0 18px;
  border-radius: 999px;
  line-height: 1;
  white-space: nowrap;
}

.login-link.ant-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.login-link.ant-btn :deep(span) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.login-link-text {
  background: #0a7152;
  color: #ffffff;
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

  .layout-sidebar,
  .layout-main {
    height: auto;
  }

  .layout-main {
    overflow: visible;
    padding: 16px;
  }

  .menu-list,
  .content-panel {
    overflow: visible;
    min-height: auto;
  }

  .topbar {
    flex-direction: column;
    align-items: flex-start;
  }

  .action-group {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
