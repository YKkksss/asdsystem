<template>
  <section class="notification-page">
    <div class="summary-grid">
      <a-card :bordered="false" class="summary-card">
        <span>消息总数</span>
        <strong>{{ summary.total_count }}</strong>
        <small>当前账号可查看的站内消息总数</small>
      </a-card>
      <a-card :bordered="false" class="summary-card">
        <span>未读消息</span>
        <strong>{{ summary.unread_count }}</strong>
        <small>仍未确认阅读的通知数量</small>
      </a-card>
      <a-card :bordered="false" class="summary-card">
        <span>催还未读</span>
        <strong>{{ summary.reminder_unread_count }}</strong>
        <small>借阅催还相关未读消息数量</small>
      </a-card>
    </div>

    <a-card :bordered="false" class="panel-card">
      <div class="toolbar-grid">
        <a-select
          v-model:value="filters.notification_type"
          allow-clear
          class="toolbar-select"
          placeholder="通知类型"
          :options="typeOptions"
        />

        <a-select
          v-model:value="filters.is_read"
          allow-clear
          class="toolbar-select"
          placeholder="阅读状态"
          :options="readOptions"
        />
      </div>

      <div class="toolbar-actions">
        <a-space wrap>
          <a-button @click="handleReset">重置筛选</a-button>
          <a-button type="primary" @click="loadPageData">刷新消息</a-button>
          <a-button
            v-if="summary.unread_count > 0"
            :loading="markingAllRead"
            @click="handleMarkAllRead"
          >
            全部标记已读
          </a-button>
        </a-space>

        <a-button
          v-if="canDispatchReminders"
          type="primary"
          :loading="dispatching"
          @click="handleDispatchReminders"
        >
          执行催还扫描
        </a-button>
      </div>

      <a-table
        :columns="columns"
        :data-source="notifications"
        :loading="loading"
        row-key="id"
        :row-class-name="getNotificationRowClassName"
        :pagination="{
          current: notificationPagination.current,
          pageSize: notificationPagination.pageSize,
          total: notificationPagination.total,
          showSizeChanger: true,
          pageSizeOptions: ['8', '20', '50'],
          onChange: handleNotificationTableChange,
          onShowSizeChange: handleNotificationTableChange,
          showTotal: (total: number) => `共 ${total} 条`,
        }"
      >
        <template #emptyText>
          <a-empty description="暂无通知消息" />
        </template>

        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'title'">
            <div class="title-cell">
              <strong>{{ record.title }}</strong>
              <span>{{ record.content }}</span>
            </div>
          </template>

          <template v-else-if="column.key === 'notification_type'">
            <a-tag :color="typeColorMap[record.notification_type] || 'default'">
              {{ typeLabelMap[record.notification_type] || record.notification_type }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'is_read'">
            <a-tag :color="record.is_read ? 'green' : 'gold'">
              {{ record.is_read ? "已读" : "未读" }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'created_at'">
            {{ formatDateTime(record.created_at) }}
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-space wrap>
              <a-button
                v-if="canOpenBusiness(record)"
                type="link"
                :loading="openingId === record.id"
                @click="handleOpenBusiness(record)"
              >
                查看业务
              </a-button>
              <a-button
                v-if="!record.is_read"
                type="link"
                :loading="markingId === record.id"
                @click="handleMarkRead(record.id)"
              >
                标记已读
              </a-button>
              <span v-else-if="!canOpenBusiness(record)" class="action-muted">已处理</span>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue"
import { message } from "ant-design-vue"
import { useRoute, useRouter } from "vue-router"

import { dispatchBorrowReminders } from "@/api/borrowing"
import {
  fetchNotificationPosition,
  fetchNotificationsPage,
  fetchNotificationSummary,
  markAllNotificationsAsRead,
  markNotificationAsRead,
  type NotificationSummary,
  type SystemNotification,
} from "@/api/notifications"
import { useAuthStore } from "@/stores/auth"
import { ARCHIVE_MANAGER_FALLBACK_ROLES, profileHasAnyPermission } from "@/utils/access"

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const canDispatchReminders = computed(() =>
  profileHasAnyPermission(
    authStore.profile,
    ["button.notification.reminder.dispatch"],
    ARCHIVE_MANAGER_FALLBACK_ROLES,
  ),
)

const typeLabelMap: Record<string, string> = {
  BORROW_APPROVAL: "借阅审批通知",
  BORROW_REMINDER: "催还通知",
  RETURN_CONFIRM: "归还确认通知",
  DESTROY_APPROVAL: "销毁审批通知",
  SYSTEM: "系统通知",
}

const typeColorMap: Record<string, string> = {
  BORROW_APPROVAL: "blue",
  BORROW_REMINDER: "volcano",
  RETURN_CONFIRM: "green",
  DESTROY_APPROVAL: "purple",
  SYSTEM: "default",
}

const typeOptions = Object.entries(typeLabelMap).map(([value, label]) => ({ value, label }))
const readOptions = [
  { value: true, label: "已读" },
  { value: false, label: "未读" },
]

const columns = [
  { title: "消息内容", key: "title" },
  { title: "通知类型", key: "notification_type", width: 150 },
  { title: "阅读状态", key: "is_read", width: 120 },
  { title: "创建时间", key: "created_at", width: 180 },
  { title: "操作", key: "actions", width: 120 },
]

const loading = ref(false)
const dispatching = ref(false)
const markingId = ref<number | null>(null)
const openingId = ref<number | null>(null)
const markingAllRead = ref(false)
const notifications = ref<SystemNotification[]>([])
const focusedNotificationId = ref<number | null>(null)
const notificationPagination = reactive({
  current: 1,
  pageSize: 8,
  total: 0,
})
const summary = reactive<NotificationSummary>({
  total_count: 0,
  unread_count: 0,
  reminder_unread_count: 0,
})

const filters = reactive({
  notification_type: undefined as string | undefined,
  is_read: undefined as boolean | undefined,
})

function formatDateTime(value: string | null) {
  if (!value) {
    return "-"
  }
  return value.replace("T", " ").slice(0, 19)
}

function handleReset() {
  filters.notification_type = undefined
  filters.is_read = undefined
  notificationPagination.current = 1
  focusedNotificationId.value = null
  void loadPageData()
}

function handleNotificationTableChange(page: number, pageSize: number) {
  notificationPagination.current = page
  notificationPagination.pageSize = pageSize
  focusedNotificationId.value = null
  void loadNotifications()
}

function canOpenBusiness(notification: SystemNotification) {
  return Boolean(notification.route_path && !notification.route_path.startsWith("/notifications/messages"))
}

function resolveRouteNotificationId() {
  const rawNotificationId = route.query.notificationId
  const notificationId = Number(rawNotificationId)
  if (!Number.isInteger(notificationId) || notificationId <= 0) {
    return null
  }
  return notificationId
}

async function clearFocusedNotificationQuery() {
  if (!route.query.notificationId) {
    return
  }
  const nextQuery = { ...route.query }
  delete nextQuery.notificationId
  await router.replace({ query: nextQuery })
}

async function scrollToFocusedNotification() {
  await nextTick()
  window.setTimeout(() => {
    const row = document.querySelector<HTMLElement>(
      `.ant-table-row[data-row-key="${focusedNotificationId.value}"]`,
    )
    row?.scrollIntoView({ behavior: "smooth", block: "center" })
  }, 80)
}

async function focusNotificationById(notificationId: number) {
  filters.notification_type = undefined
  filters.is_read = undefined

  try {
    const response = await fetchNotificationPosition(notificationId, notificationPagination.pageSize)
    notificationPagination.current = response.data.page
    await loadPageData()
    focusedNotificationId.value = notificationId
    await scrollToFocusedNotification()
    await clearFocusedNotificationQuery()
  } catch (error) {
    handleRequestError(error, "定位通知失败。")
  }
}

function getNotificationRowClassName(record: SystemNotification) {
  return record.id === focusedNotificationId.value ? "notification-row-focused" : ""
}

async function loadNotifications() {
  loading.value = true
  try {
    const response = await fetchNotificationsPage({
      notification_type: filters.notification_type,
      is_read: filters.is_read,
      page: notificationPagination.current,
      page_size: notificationPagination.pageSize,
    })
    notifications.value = response.data.items
    notificationPagination.total = response.data.pagination.total
    notificationPagination.current = response.data.pagination.page
    notificationPagination.pageSize = response.data.pagination.page_size
  } catch (error) {
    handleRequestError(error, "加载通知消息失败。")
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  try {
    const response = await fetchNotificationSummary()
    summary.total_count = response.data.total_count
    summary.unread_count = response.data.unread_count
    summary.reminder_unread_count = response.data.reminder_unread_count
  } catch (error) {
    handleRequestError(error, "加载通知汇总失败。")
  }
}

async function loadPageData() {
  await Promise.all([loadNotifications(), loadSummary()])
}

async function handleMarkRead(notificationId: number) {
  markingId.value = notificationId
  try {
    const response = await markNotificationAsRead(notificationId)
    message.success(response.message)
    await loadPageData()
  } catch (error) {
    handleRequestError(error, "标记通知已读失败。")
  } finally {
    markingId.value = null
  }
}

async function handleMarkAllRead() {
  markingAllRead.value = true
  try {
    const response = await markAllNotificationsAsRead()
    message.success(`${response.message}，共处理 ${response.data.updated_count} 条未读消息。`)
    await loadPageData()
  } catch (error) {
    handleRequestError(error, "批量标记通知已读失败。")
  } finally {
    markingAllRead.value = false
  }
}

async function handleOpenBusiness(notification: SystemNotification) {
  if (!canOpenBusiness(notification)) {
    message.warning("当前通知没有可跳转的业务页面。")
    return
  }

  openingId.value = notification.id
  try {
    if (!notification.is_read) {
      try {
        await markNotificationAsRead(notification.id)
      } catch (error) {
        handleRequestError(error, "标记通知已读失败，将继续为你打开业务页面。")
      }
    }
    await router.push(notification.route_path)
  } finally {
    openingId.value = null
  }
}

async function handleDispatchReminders() {
  if (!canDispatchReminders.value) {
    message.warning("当前账号无权执行催还扫描。")
    return
  }

  dispatching.value = true
  try {
    const response = await dispatchBorrowReminders()
    message.success(`${response.message}，本次生成 ${response.data.record_count} 条提醒记录。`)
    await loadPageData()
  } catch (error) {
    handleRequestError(error, "执行催还扫描失败。")
  } finally {
    dispatching.value = false
  }
}

function handleRequestError(error: unknown, fallbackMessage: string) {
  if (typeof error === "object" && error !== null && "response" in error) {
    const response = (error as { response?: { data?: { message?: string } } }).response
    message.error(response?.data?.message || fallbackMessage)
    return
  }
  message.error(fallbackMessage)
}

onMounted(() => {
  const notificationId = resolveRouteNotificationId()
  if (notificationId) {
    void focusNotificationById(notificationId)
    return
  }
  void loadPageData()
})

watch(
  () => route.query.notificationId,
  (value, oldValue) => {
    if (!value || value === oldValue) {
      return
    }
    const notificationId = resolveRouteNotificationId()
    if (!notificationId) {
      return
    }
    void focusNotificationById(notificationId)
  },
)
</script>

<style scoped>
.notification-page {
  display: grid;
  gap: 20px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.summary-card,
.panel-card {
  border-radius: 24px;
}

.summary-card strong {
  display: block;
  margin: 12px 0 6px;
  font-size: 26px;
}

.summary-card span,
.summary-card small {
  color: #475467;
}

.toolbar-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 220px));
  gap: 12px;
}

.toolbar-select {
  width: 100%;
}

.toolbar-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin: 16px 0;
}

.title-cell {
  display: grid;
  gap: 6px;
}

.title-cell span,
.action-muted {
  color: #667085;
}

:deep(.notification-row-focused > td) {
  background: rgba(230, 244, 255, 0.88) !important;
}

:deep(.notification-row-focused:hover > td) {
  background: rgba(186, 224, 255, 0.92) !important;
}

@media (max-width: 720px) {
  .toolbar-actions {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
