<template>
  <section class="detail-page">
    <template v-if="canViewScanTasks">
      <div class="page-actions">
        <RouterLink to="/digitization/scan-tasks">
          <a-button>返回任务列表</a-button>
        </RouterLink>
        <a-button @click="loadTaskDetail">刷新</a-button>
      </div>

      <a-card :bordered="false" class="detail-card">
        <a-spin :spinning="loading">
          <template v-if="taskDetail">
            <a-descriptions :column="3" bordered size="small" title="任务概览">
              <a-descriptions-item label="任务编号">{{ taskDetail.task_no }}</a-descriptions-item>
              <a-descriptions-item label="任务名称">{{ taskDetail.task_name }}</a-descriptions-item>
              <a-descriptions-item label="当前状态">
                <a-tag :color="statusColorMap[taskDetail.status] || 'default'">
                  {{ statusLabelMap[taskDetail.status] || taskDetail.status }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="执行人">
                {{ taskDetail.assigned_user_name || `用户 ${taskDetail.assigned_user_id}` }}
              </a-descriptions-item>
              <a-descriptions-item label="完成进度">
                {{ taskDetail.completed_count }}/{{ taskDetail.total_count }}
              </a-descriptions-item>
              <a-descriptions-item label="失败数">{{ taskDetail.failed_count }}</a-descriptions-item>
              <a-descriptions-item :span="3" label="备注">
                {{ taskDetail.remark || "暂无备注" }}
              </a-descriptions-item>
            </a-descriptions>

            <a-alert
              class="upload-guide"
              show-icon
              :type="canManageScanTasks ? 'info' : 'warning'"
              :message="canManageScanTasks ? `上传支持 PDF、JPG、JPEG、PNG、TIF、TIFF，单个文件不超过 ${scanUploadMaxSizeMb} MB。` : '当前账号仅可查看任务详情，不能上传或处理扫描文件。'"
            />

            <div class="item-grid">
              <a-card
                v-for="item in taskDetail.items"
                :key="item.id"
                :bordered="false"
                class="item-card"
                :class="{ 'item-card-focused': item.id === focusedItemId }"
                :data-item-id="item.id"
              >
                <div class="item-header">
                  <div>
                    <strong>{{ item.archive_title }}</strong>
                    <p>{{ item.archive_code }}</p>
                  </div>
                  <a-tag :color="itemStatusColorMap[item.status] || 'default'">
                    {{ itemStatusLabelMap[item.status] || item.status }}
                  </a-tag>
                </div>

                <div class="item-metrics">
                  <span>档案状态：{{ archiveStatusLabelMap[item.archive_status] || item.archive_status }}</span>
                  <span>已上传文件：{{ item.uploaded_file_count }}</span>
                  <span>最后上传：{{ formatDateTime(item.last_uploaded_at) }}</span>
                </div>

                <div v-if="canManageScanTasks" class="upload-block">
                  <input
                    :id="`scan-file-${item.id}`"
                    class="upload-input"
                    multiple
                    type="file"
                    :accept="scanUploadAccept"
                    @change="handleSelectFiles(item.id, $event)"
                  />
                  <label :for="`scan-file-${item.id}`" class="upload-label">选择文件</label>
                  <div v-if="selectedFileMap[item.id]?.length" class="selected-file-list">
                    <span v-for="file in selectedFileMap[item.id]" :key="file.name">
                      {{ file.name }}
                    </span>
                  </div>
                  <a-button
                    type="primary"
                    :loading="uploadingItemId === item.id"
                    @click="handleUpload(item.id)"
                  >
                    上传并处理
                  </a-button>
                </div>

                <a-alert
                  v-if="item.error_message"
                  :message="item.error_message"
                  show-icon
                  type="error"
                  class="item-alert"
                />

                <div class="file-list">
                  <template v-if="item.files.length">
                    <article v-for="file in item.files" :key="file.id" class="file-card">
                      <div class="file-card-header">
                        <strong>{{ file.file_name }}</strong>
                        <a-tag :color="file.status === 'ACTIVE' ? 'green' : file.status === 'FAILED' ? 'red' : 'blue'">
                          {{ file.status }}
                        </a-tag>
                      </div>
                      <a-image
                        v-if="file.thumbnail_path"
                        :src="buildArchiveAssetUrl(file.thumbnail_path)"
                        :preview="true"
                        class="file-thumbnail"
                      />
                      <div class="file-card-meta">
                        <span>扩展名：{{ file.file_ext }}</span>
                        <span>页数：{{ file.page_count || "-" }}</span>
                        <span>大小：{{ formatFileSize(file.file_size) }}</span>
                      </div>
                      <p v-if="file.extracted_text" class="file-text-snippet">
                        {{ file.extracted_text.slice(0, 120) }}
                      </p>
                    </article>
                  </template>
                  <a-empty v-else description="当前明细尚未上传文件" />
                </div>
              </a-card>
            </div>
          </template>
        </a-spin>
      </a-card>
    </template>

    <a-result
      v-else
      status="403"
      title="仅具备数字化任务权限的账号可查看扫描任务详情"
      sub-title="请联系管理员分配数字化任务权限，或返回档案检索页查看当前已授权数据。"
    >
      <template #extra>
        <RouterLink to="/archives/records">
          <a-button type="primary">返回档案检索</a-button>
        </RouterLink>
      </template>
    </a-result>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from "vue"
import { message } from "ant-design-vue"
import { RouterLink, useRoute, useRouter } from "vue-router"

import { buildArchiveAssetUrl } from "@/api/archives"
import {
  fetchScanTaskDetail,
  scanUploadAccept,
  scanUploadMaxSizeMb,
  uploadScanTaskItemFiles,
  validateScanUploadFiles,
  type ScanTaskDetail,
} from "@/api/digitization"
import { useAuthStore } from "@/stores/auth"
import { ARCHIVE_MANAGER_FALLBACK_ROLES, profileHasAnyPermission } from "@/utils/access"

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const canViewScanTasks = computed(() =>
  profileHasAnyPermission(
    authStore.profile,
    ["menu.scan_task", "button.scan_task.manage"],
    ARCHIVE_MANAGER_FALLBACK_ROLES,
  ),
)

const canManageScanTasks = computed(() =>
  profileHasAnyPermission(authStore.profile, ["button.scan_task.manage"], ARCHIVE_MANAGER_FALLBACK_ROLES),
)

const statusLabelMap: Record<string, string> = {
  PENDING: "待开始",
  IN_PROGRESS: "进行中",
  COMPLETED: "已完成",
  FAILED: "已失败",
}

const statusColorMap: Record<string, string> = {
  PENDING: "default",
  IN_PROGRESS: "blue",
  COMPLETED: "green",
  FAILED: "red",
}

const itemStatusLabelMap: Record<string, string> = {
  PENDING: "待上传",
  PROCESSING: "处理中",
  COMPLETED: "已完成",
  FAILED: "已失败",
}

const itemStatusColorMap: Record<string, string> = {
  PENDING: "default",
  PROCESSING: "blue",
  COMPLETED: "green",
  FAILED: "red",
}

const archiveStatusLabelMap: Record<string, string> = {
  DRAFT: "草稿",
  PENDING_SCAN: "待扫描",
  PENDING_CATALOG: "待编目",
  ON_SHELF: "已上架",
  BORROWED: "借出中",
  DESTROY_PENDING: "销毁审批中",
  DESTROYED: "已销毁",
  FROZEN: "冻结",
}

const loading = ref(false)
const uploadingItemId = ref<number | null>(null)
const taskDetail = ref<ScanTaskDetail | null>(null)
const selectedFileMap = reactive<Record<number, File[]>>({})
const focusedItemId = ref<number | null>(null)

function formatDateTime(value: string | null) {
  if (!value) {
    return "-"
  }
  return value.replace("T", " ").slice(0, 19)
}

function formatFileSize(size: number) {
  if (size < 1024) {
    return `${size} B`
  }
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }
  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

function getTaskId() {
  return Number(route.params.taskId)
}

function resolveRouteItemId() {
  const rawItemId = route.query.itemId
  const itemId = Number(rawItemId)
  if (!Number.isInteger(itemId) || itemId <= 0) {
    return null
  }
  return itemId
}

async function clearRouteItemId() {
  if (!route.query.itemId) {
    return
  }
  const nextQuery = { ...route.query }
  delete nextQuery.itemId
  await router.replace({ query: nextQuery })
}

async function scrollToFocusedItem() {
  await nextTick()
  window.setTimeout(() => {
    const element = document.querySelector<HTMLElement>(`.item-card[data-item-id="${focusedItemId.value}"]`)
    element?.scrollIntoView({ behavior: "smooth", block: "center" })
  }, 80)
}

async function focusTaskItemFromRoute() {
  const itemId = resolveRouteItemId()
  if (!itemId) {
    if (focusedItemId.value && taskDetail.value?.items.some((item) => item.id === focusedItemId.value)) {
      return
    }
    focusedItemId.value = null
    return
  }

  const targetExists = taskDetail.value?.items.some((item) => item.id === itemId)
  if (!targetExists) {
    focusedItemId.value = null
    await clearRouteItemId()
    message.warning("目标扫描明细不存在或已被移除。")
    return
  }

  focusedItemId.value = itemId
  await scrollToFocusedItem()
  await clearRouteItemId()
}

function resetFileInput(itemId: number) {
  const input = document.getElementById(`scan-file-${itemId}`) as HTMLInputElement | null
  if (input) {
    input.value = ""
  }
}

async function loadTaskDetail() {
  const taskId = getTaskId()
  if (!taskId) {
    message.error("任务编号无效。")
    await router.push("/digitization/scan-tasks")
    return
  }

  loading.value = true
  try {
    const response = await fetchScanTaskDetail(taskId)
    taskDetail.value = response.data
    await focusTaskItemFromRoute()
  } catch (error) {
    const response = (error as { response?: { status?: number } }).response
    if (response?.status === 404) {
      message.error("扫描任务不存在或已被删除。")
      await router.push("/digitization/scan-tasks")
      return
    }
    handleRequestError(error, "加载扫描任务详情失败。")
  } finally {
    loading.value = false
  }
}

function handleSelectFiles(itemId: number, event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  const validationMessage = validateScanUploadFiles(files)
  if (validationMessage) {
    selectedFileMap[itemId] = []
    input.value = ""
    message.warning(validationMessage)
    return
  }
  selectedFileMap[itemId] = files
}

async function handleUpload(itemId: number) {
  if (!canManageScanTasks.value) {
    message.warning("当前账号无权上传扫描文件。")
    return
  }

  const files = selectedFileMap[itemId] || []
  if (!files.length) {
    message.warning("请先选择要上传的文件。")
    return
  }
  const validationMessage = validateScanUploadFiles(files)
  if (validationMessage) {
    selectedFileMap[itemId] = []
    resetFileInput(itemId)
    message.warning(validationMessage)
    return
  }

  uploadingItemId.value = itemId
  try {
    const response = await uploadScanTaskItemFiles(itemId, files)
    taskDetail.value = response.data
    selectedFileMap[itemId] = []
    resetFileInput(itemId)
    message.success(response.message)
  } catch (error) {
    handleRequestError(error, "上传扫描文件失败。")
  } finally {
    uploadingItemId.value = null
  }
}

function handleRequestError(error: unknown, fallbackMessage: string) {
  if (typeof error === "object" && error !== null && "response" in error) {
    const response = (error as { response?: { data?: { message?: string }; status?: number } }).response
    if (response?.status === 403) {
      message.error("当前账号无权维护扫描任务。")
      return
    }
    message.error(response?.data?.message || fallbackMessage)
    return
  }
  message.error(fallbackMessage)
}

watch(
  () => [route.params.taskId, canViewScanTasks.value],
  async ([, canView]) => {
    if (!canView) {
      taskDetail.value = null
      focusedItemId.value = null
      Object.keys(selectedFileMap).forEach((key) => {
        delete selectedFileMap[Number(key)]
      })
      return
    }
    await loadTaskDetail()
  },
  { immediate: true },
)

watch(
  () => route.query.itemId,
  (value, oldValue) => {
    if (!value || value === oldValue) {
      return
    }
    if (!canViewScanTasks.value || !taskDetail.value) {
      return
    }
    void focusTaskItemFromRoute()
  },
)
</script>

<style scoped>
.detail-page {
  display: grid;
  gap: 16px;
}

.page-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.detail-card {
  border-radius: 24px;
}

.upload-guide {
  margin-top: 16px;
}

.item-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 16px;
  margin-top: 20px;
}

.item-card {
  border-radius: 22px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(246, 249, 255, 0.92));
}

.item-card-focused {
  box-shadow: 0 0 0 3px rgba(22, 119, 255, 0.14);
}

.item-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.item-header p {
  margin: 6px 0 0;
  color: #667085;
  font-size: 12px;
}

.item-metrics {
  display: grid;
  gap: 6px;
  margin: 16px 0;
  color: #475467;
  font-size: 13px;
}

.upload-block {
  display: grid;
  gap: 10px;
  margin-bottom: 14px;
}

.upload-input {
  display: none;
}

.upload-label {
  width: fit-content;
  padding: 10px 14px;
  border: 1px dashed rgba(21, 94, 239, 0.32);
  border-radius: 14px;
  color: #155eef;
  cursor: pointer;
}

.selected-file-list {
  display: grid;
  gap: 6px;
  color: #667085;
  font-size: 12px;
}

.item-alert {
  margin-bottom: 14px;
}

.file-list {
  display: grid;
  gap: 12px;
}

.file-card {
  padding: 14px;
  border: 1px solid rgba(21, 94, 239, 0.12);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.86);
}

.file-card-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.file-thumbnail {
  margin-top: 10px;
}

.file-card-meta {
  display: grid;
  gap: 4px;
  margin-top: 10px;
  color: #667085;
  font-size: 12px;
}

.file-text-snippet {
  margin: 10px 0 0;
  color: #475467;
  line-height: 1.7;
}

@media (max-width: 768px) {
  .page-actions {
    flex-direction: column;
  }
}
</style>
