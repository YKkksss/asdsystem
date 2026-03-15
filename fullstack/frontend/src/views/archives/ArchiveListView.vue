<template>
  <section class="archive-page">
    <div class="summary-grid">
      <a-card v-for="item in summaryCards" :key="item.label" :bordered="false" class="summary-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.caption }}</small>
      </a-card>
    </div>

    <a-card :bordered="false" class="panel-card">
      <div class="toolbar-grid">
        <a-input-search
          v-model:value="filters.keyword"
          allow-clear
          class="toolbar-search"
          placeholder="按档号、题名、关键词、摘要或提取文本搜索"
          @search="handleApplyFilters"
        />

        <a-input
          v-model:value="filters.archive_code"
          allow-clear
          placeholder="按档号精确缩小范围"
        />

        <a-input-number
          v-model:value="filters.year"
          :min="1000"
          :max="9999"
          class="toolbar-input"
          placeholder="年度"
        />

        <a-select
          v-model:value="filters.retention_period"
          allow-clear
          class="toolbar-select"
          placeholder="保管期限"
          :options="retentionOptions"
        />

        <a-select
          v-model:value="filters.security_level"
          allow-clear
          class="toolbar-select"
          placeholder="密级"
          :options="securityOptions"
        />

        <a-select
          v-model:value="filters.status"
          allow-clear
          class="toolbar-select"
          placeholder="状态"
          :options="statusFilterOptions"
        />

        <a-select
          v-model:value="filters.responsible_dept_id"
          allow-clear
          class="toolbar-select"
          placeholder="责任部门"
          :options="departmentOptions"
          :loading="optionsLoading"
          show-search
          :filter-option="filterOption"
        />

        <a-select
          v-if="canManageArchives"
          v-model:value="filters.location_id"
          allow-clear
          class="toolbar-select"
          placeholder="实体位置"
          :options="locationOptions"
          :loading="optionsLoading"
          show-search
          :filter-option="filterOption"
        />
      </div>

      <div class="toolbar-actions">
        <a-space wrap>
          <a-button @click="handleResetFilters">重置筛选</a-button>
          <a-button type="primary" @click="handleApplyFilters">执行检索</a-button>
          <a-button @click="loadArchives">刷新</a-button>
        </a-space>

        <a-space v-if="canManageArchives" wrap>
          <span class="selection-hint">已选 {{ selectedArchiveIds.length }} 条</span>
          <a-button :disabled="!selectedArchiveIds.length" @click="handleBatchPrint">
            批量打印
          </a-button>
          <RouterLink to="/archives/records/create">
            <a-button type="primary">新建档案</a-button>
          </RouterLink>
        </a-space>
      </div>

      <a-table
        :columns="columns"
        :data-source="archives"
        :loading="loading"
        row-key="id"
        :row-selection="rowSelection"
        :pagination="{
          current: archivePagination.current,
          pageSize: archivePagination.pageSize,
          total: archivePagination.total,
          showSizeChanger: true,
          pageSizeOptions: ['8', '20', '50'],
          onChange: handleArchiveTableChange,
          onShowSizeChange: handleArchiveTableChange,
          showTotal: (total: number) => `共 ${total} 条`,
        }"
      >
        <template #emptyText>
          <a-empty description="暂无匹配的档案记录" />
        </template>

        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'title'">
            <div class="title-cell">
              <strong>{{ record.title }}</strong>
              <span>{{ record.archive_code }}</span>
              <a-tag v-if="record.is_sensitive_masked" color="gold">已脱敏</a-tag>
            </div>
          </template>

          <template v-else-if="column.key === 'status'">
            <a-tag :color="statusColorMap[record.status] || 'default'">
              {{ statusLabelMap[record.status] || record.status }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'security_level'">
            <a-tag color="gold">{{ securityLabelMap[record.security_level] || record.security_level }}</a-tag>
          </template>

          <template v-else-if="column.key === 'responsible_person'">
            <div class="responsible-cell">
              <strong>{{ record.responsible_person || "未填写" }}</strong>
              <span>{{ record.responsible_dept_name || "未指定部门" }}</span>
            </div>
          </template>

          <template v-else-if="column.key === 'location'">
            <span>{{ record.location_detail?.full_location_code || "未绑定位置" }}</span>
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-space wrap>
              <a-button type="link" @click="openDetail(record.id)">查看详情</a-button>
              <a-button v-if="canManageArchives" type="link" @click="openEdit(record.id)">
                编辑
              </a-button>
              <a-button
                v-if="canManageArchives"
                :loading="actionLoadingId === record.id"
                type="link"
                @click="handleGenerateCodes(record.id)"
              >
                生成码
              </a-button>
              <a-button v-if="canManageArchives" type="link" @click="openPrintPage([record.id])">
                打印
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-drawer
      v-model:open="detailOpen"
      :width="760"
      title="档案详情"
      :destroy-on-close="false"
    >
      <a-spin :spinning="detailLoading">
        <template v-if="selectedArchive">
          <a-alert
            v-if="selectedArchive.is_sensitive_masked"
            type="warning"
            show-icon
            class="detail-alert"
            message="当前账号密级不足，摘要、责任者、文件与实体精确位置已由后端脱敏。"
          />

          <a-descriptions :column="2" bordered size="small">
            <a-descriptions-item label="档号">{{ selectedArchive.archive_code }}</a-descriptions-item>
            <a-descriptions-item label="题名">{{ selectedArchive.title }}</a-descriptions-item>
            <a-descriptions-item label="年度">{{ selectedArchive.year }}</a-descriptions-item>
            <a-descriptions-item label="保管期限">{{ selectedArchive.retention_period }}</a-descriptions-item>
            <a-descriptions-item label="密级">
              {{ securityLabelMap[selectedArchive.security_level] || selectedArchive.security_level }}
            </a-descriptions-item>
            <a-descriptions-item label="当前状态">
              {{ statusLabelMap[selectedArchive.status] || selectedArchive.status }}
            </a-descriptions-item>
            <a-descriptions-item label="责任部门">
              {{ selectedArchive.responsible_dept_name || "未填写" }}
            </a-descriptions-item>
            <a-descriptions-item label="责任人">
              {{ selectedArchive.responsible_person || "未填写" }}
            </a-descriptions-item>
            <a-descriptions-item :span="2" label="实体位置">
              {{ selectedArchive.location_detail?.full_location_code || "未绑定位置" }}
            </a-descriptions-item>
            <a-descriptions-item :span="2" label="摘要">
              {{ selectedArchive.summary || "暂无摘要" }}
            </a-descriptions-item>
          </a-descriptions>

          <a-card v-if="canManageArchives" class="detail-block" size="small" title="状态流转">
            <a-alert
              show-icon
              type="info"
              message="状态流转会同步写入编目修订记录。"
              class="transition-alert"
            />

            <div class="transition-form">
              <a-select
                v-model:value="transitionForm.next_status"
                allow-clear
                class="transition-input"
                placeholder="选择目标状态"
                :options="availableTransitionOptions"
              />
              <a-input-number
                v-if="transitionForm.next_status === 'BORROWED'"
                v-model:value="transitionForm.current_borrow_id"
                :min="1"
                class="transition-input"
                placeholder="请输入借阅单 ID"
              />
              <a-input
                v-model:value="transitionForm.remark"
                class="transition-input transition-remark"
                placeholder="补充说明，例如：提交扫描、编目通过"
              />
              <a-button type="primary" :loading="transitionSubmitting" @click="handleTransitionStatus">
                提交流转
              </a-button>
            </div>
          </a-card>

          <a-card class="detail-block" size="small" title="条码与二维码">
            <template #extra>
              <a-button
                v-if="canManageArchives"
                type="primary"
                :disabled="!selectedArchive.barcodes.length"
                @click="openPrintPage([selectedArchive.id])"
              >
                打印标签
              </a-button>
            </template>
            <template v-if="selectedArchive.barcodes.length">
              <div class="barcode-grid">
                <div v-for="item in selectedArchive.barcodes" :key="item.id" class="barcode-card">
                  <strong>{{ item.code_type === "BARCODE" ? "条码" : "二维码" }}</strong>
                  <a-image
                    v-if="item.image_path"
                    :src="buildArchiveAssetUrl(item.image_path)"
                    :preview="true"
                    class="barcode-image"
                  />
                  <span>{{ item.code_content }}</span>
                  <small>已打印 {{ item.print_count }} 次</small>
                  <small>最后打印：{{ formatDateTime(item.last_printed_at) }}</small>
                </div>
              </div>
            </template>
            <a-empty v-else description="尚未生成条码或二维码" />
          </a-card>

          <a-card class="detail-block" size="small" title="电子文件关联">
            <a-alert
              v-if="selectedArchive.masked_fields.includes('files') && selectedArchive.files.length"
              type="warning"
              show-icon
              message="当前账号无权查看文件预览入口和提取文本。"
              class="file-alert"
            />
            <template v-if="selectedArchive.files.length && !selectedArchive.masked_fields.includes('files')">
              <div class="file-grid">
                <article v-for="file in selectedArchive.files" :key="file.id" class="file-card">
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
                  <div class="file-meta">
                    <span>扩展名：{{ file.file_ext }}</span>
                    <span>页数：{{ file.page_count || "-" }}</span>
                    <span>大小：{{ formatFileSize(file.file_size) }}</span>
                  </div>
                  <p v-if="file.extracted_text" class="file-text">
                    {{ file.extracted_text.slice(0, 120) }}
                  </p>
                  <a-space wrap>
                    <a-button
                      v-if="isPreviewSupported(file.file_ext)"
                      type="link"
                      :loading="fileAccessLoadingId === file.id && previewLoading"
                      @click="handleOpenFilePreview(file)"
                    >
                      在线预览
                    </a-button>
                    <a-button
                      type="link"
                      :loading="fileAccessLoadingId === file.id && downloadSubmitting"
                      @click="openDownloadModal(file)"
                    >
                      下载文件
                    </a-button>
                  </a-space>
                </article>
              </div>
            </template>
            <a-empty
              v-else-if="!selectedArchive.files.length"
              description="当前档案尚未关联电子文件"
            />
          </a-card>

          <a-card class="detail-block" size="small" title="修订记录">
            <template v-if="selectedArchive.revisions.length">
              <a-timeline>
                <a-timeline-item v-for="item in selectedArchive.revisions" :key="item.id">
                  <div class="revision-item">
                    <strong>版本 {{ item.revision_no }}</strong>
                    <span>{{ item.remark || "未填写说明" }}</span>
                    <small>{{ formatDateTime(item.revised_at) }}</small>
                  </div>
                </a-timeline-item>
              </a-timeline>
            </template>
            <a-empty v-else description="暂无修订记录" />
          </a-card>
        </template>
      </a-spin>
    </a-drawer>

    <a-modal
      v-model:open="previewOpen"
      :footer="null"
      :width="960"
      title="文件在线预览"
      destroy-on-close
    >
      <a-spin :spinning="previewLoading">
        <div v-if="previewSource" class="preview-shell">
          <div class="preview-watermark" :style="previewWatermarkStyle" />
          <iframe
            v-if="previewFileExt === 'pdf'"
            :src="previewSource"
            class="preview-frame"
            title="文件在线预览"
          />
          <img
            v-else
            :src="previewSource"
            :alt="previewTitle"
            class="preview-image"
          />
        </div>
      </a-spin>
    </a-modal>

    <a-modal
      v-model:open="downloadOpen"
      :confirm-loading="downloadSubmitting"
      title="下载确认"
      ok-text="确认下载"
      @ok="handleDownloadFile"
    >
      <template v-if="selectedFileForAccess">
        <a-alert
          show-icon
          type="warning"
          class="detail-alert"
          :message="`下载将写入审计日志：${selectedFileForAccess.file_name}`"
        />
        <a-form layout="vertical">
          <a-form-item label="下载用途" required>
            <a-textarea
              v-model:value="downloadPurpose"
              :rows="4"
              placeholder="请填写本次下载的业务用途，例如：工作核验、审批材料整理"
            />
          </a-form-item>
        </a-form>
      </template>
    </a-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import { message } from "ant-design-vue"
import type { SelectProps } from "ant-design-vue"
import { RouterLink, useRouter } from "vue-router"

import {
  buildArchiveAccessUrl,
  buildArchiveAssetUrl,
  createArchiveFileDownloadTicket,
  createArchiveFilePreviewTicket,
  fetchArchiveDetail,
  fetchArchiveLocations,
  fetchArchives,
  fetchArchivesPage,
  generateArchiveCodes,
  transitionArchiveStatus,
  type ArchiveFile,
  type ArchiveRecord,
  type ArchiveRecordDetail,
} from "@/api/archives"
import { fetchDepartments } from "@/api/organizations"
import { useAuthStore } from "@/stores/auth"

const authStore = useAuthStore()
const router = useRouter()

const statusLabelMap: Record<string, string> = {
  DRAFT: "草稿",
  PENDING_SCAN: "待扫描",
  PENDING_CATALOG: "待编目",
  ON_SHELF: "已上架",
  BORROWED: "借出中",
  DESTROY_PENDING: "销毁审批中",
  DESTROYED: "已销毁",
  FROZEN: "冻结",
}

const statusColorMap: Record<string, string> = {
  DRAFT: "default",
  PENDING_SCAN: "cyan",
  PENDING_CATALOG: "blue",
  ON_SHELF: "green",
  BORROWED: "orange",
  DESTROY_PENDING: "volcano",
  DESTROYED: "red",
  FROZEN: "purple",
}

const securityLabelMap: Record<string, string> = {
  PUBLIC: "公开",
  INTERNAL: "内部",
  SECRET: "秘密",
  CONFIDENTIAL: "机密",
  TOP_SECRET: "绝密",
}

const retentionOptions = [
  { value: "永久", label: "永久" },
  { value: "长期", label: "长期" },
  { value: "30年", label: "30年" },
  { value: "10年", label: "10年" },
]

const securityOptions = Object.entries(securityLabelMap).map(([value, label]) => ({ value, label }))
const statusFilterOptions = Object.entries(statusLabelMap).map(([value, label]) => ({ value, label }))

const statusTransitionMap: Record<string, string[]> = {
  DRAFT: ["PENDING_SCAN", "PENDING_CATALOG", "FROZEN"],
  PENDING_SCAN: ["PENDING_CATALOG", "FROZEN"],
  PENDING_CATALOG: ["ON_SHELF", "FROZEN"],
  ON_SHELF: ["BORROWED", "DESTROY_PENDING", "FROZEN"],
  BORROWED: ["ON_SHELF", "FROZEN"],
  DESTROY_PENDING: ["DESTROYED", "ON_SHELF", "FROZEN"],
  FROZEN: ["DRAFT", "PENDING_SCAN", "PENDING_CATALOG", "ON_SHELF", "DESTROY_PENDING"],
}

const columns = [
  { title: "档案信息", key: "title" },
  { title: "年度", dataIndex: "year", key: "year", width: 96 },
  { title: "保管期限", dataIndex: "retention_period", key: "retention_period", width: 110 },
  { title: "密级", key: "security_level", dataIndex: "security_level", width: 100 },
  { title: "状态", key: "status", dataIndex: "status", width: 120 },
  { title: "责任信息", key: "responsible_person", width: 180 },
  { title: "实体位置", key: "location", width: 220 },
  { title: "操作", key: "actions", width: 280, fixed: "right" as const },
]

const canManageArchives = computed(() =>
  Boolean(authStore.profile?.roles.some((role) => ["ADMIN", "ARCHIVIST"].includes(role.role_code))),
)

const loading = ref(false)
const detailLoading = ref(false)
const optionsLoading = ref(false)
const transitionSubmitting = ref(false)
const actionLoadingId = ref<number | null>(null)
const fileAccessLoadingId = ref<number | null>(null)
const detailOpen = ref(false)
const previewOpen = ref(false)
const previewLoading = ref(false)
const downloadOpen = ref(false)
const downloadSubmitting = ref(false)
const archives = ref<ArchiveRecord[]>([])
const selectedArchiveIds = ref<number[]>([])
const selectedArchive = ref<ArchiveRecordDetail | null>(null)
const selectedFileForAccess = ref<ArchiveFile | null>(null)
const departmentOptions = ref<SelectProps["options"]>([])
const locationOptions = ref<SelectProps["options"]>([])
const previewSource = ref("")
const previewTitle = ref("")
const previewWatermarkText = ref("")
const previewFileExt = ref("")
const downloadPurpose = ref("")
const archivePagination = reactive({
  current: 1,
  pageSize: 8,
  total: 0,
})

const initialFilters = () => ({
  keyword: "",
  archive_code: "",
  year: undefined as number | undefined,
  retention_period: undefined as string | undefined,
  security_level: undefined as string | undefined,
  status: undefined as string | undefined,
  responsible_dept_id: undefined as number | undefined,
  location_id: undefined as number | undefined,
})

const filters = reactive(initialFilters())

const transitionForm = reactive({
  next_status: undefined as string | undefined,
  current_borrow_id: undefined as number | undefined,
  remark: "",
})

const summaryCards = computed(() => {
  const total = archivePagination.total
  const maskedCount = archives.value.filter((item) => item.is_sensitive_masked).length
  const onShelfCount = archives.value.filter((item) => item.status === "ON_SHELF").length
  const pendingCount = archives.value.filter((item) =>
    ["PENDING_SCAN", "PENDING_CATALOG"].includes(item.status),
  ).length

  return [
    { label: "检索结果", value: total, caption: "当前组合条件下命中的档案数量" },
    { label: "待处理", value: pendingCount, caption: "待扫描与待编目的档案数量" },
    { label: "已上架", value: onShelfCount, caption: "已经可检索、可借阅的档案数量" },
    { label: "脱敏结果", value: maskedCount, caption: "当前账号密级不足而被后端脱敏的结果数" },
  ]
})

const rowSelection = computed(() => {
  if (!canManageArchives.value) {
    return undefined
  }

  return {
    selectedRowKeys: selectedArchiveIds.value,
    onChange: (selectedRowKeys: Array<string | number>) => {
      selectedArchiveIds.value = selectedRowKeys.map((item) => Number(item))
    },
  }
})

const availableTransitionOptions = computed(() => {
  if (!selectedArchive.value) {
    return []
  }
  return (statusTransitionMap[selectedArchive.value.status] || []).map((value) => ({
    value,
    label: statusLabelMap[value] || value,
  }))
})

const previewWatermarkStyle = computed(() => {
  if (!previewWatermarkText.value) {
    return {}
  }
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="280" height="180">
      <text x="20" y="90" fill="rgba(15,77,65,0.18)" font-size="18" transform="rotate(-24 140 90)">
        ${previewWatermarkText.value}
      </text>
    </svg>
  `
  return {
    backgroundImage: `url("data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}")`,
  }
})

function filterOption(input: string, option?: { label?: unknown }) {
  return String(option?.label || "").toLowerCase().includes(input.toLowerCase())
}

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

function isPreviewSupported(fileExt: string) {
  return ["pdf", "jpg", "jpeg", "png"].includes(fileExt.toLowerCase())
}

function resetTransitionForm() {
  transitionForm.next_status = undefined
  transitionForm.current_borrow_id = undefined
  transitionForm.remark = ""
}

function resetPreviewState() {
  previewSource.value = ""
  previewTitle.value = ""
  previewWatermarkText.value = ""
  previewFileExt.value = ""
}

function resetDownloadState() {
  selectedFileForAccess.value = null
  downloadPurpose.value = ""
}

function handleResetFilters() {
  Object.assign(filters, initialFilters())
  selectedArchiveIds.value = []
  archivePagination.current = 1
  void loadArchives()
}

function handleApplyFilters() {
  archivePagination.current = 1
  void loadArchives()
}

function handleArchiveTableChange(page: number, pageSize: number) {
  archivePagination.current = page
  archivePagination.pageSize = pageSize
  void loadArchives()
}

async function loadFilterOptions() {
  optionsLoading.value = true
  try {
    const [departmentsResponse, locationsResponse] = await Promise.all([
      fetchDepartments(),
      canManageArchives.value ? fetchArchiveLocations() : Promise.resolve({ data: [] }),
    ])
    departmentOptions.value = departmentsResponse.data.map((item) => ({
      value: item.id,
      label: `${item.dept_name}（${item.dept_code}）`,
    }))
    locationOptions.value = locationsResponse.data.map((item) => ({
      value: item.id,
      label: item.full_location_code,
    }))
  } catch (error) {
    handleRequestError(error, "加载筛选选项失败。")
  } finally {
    optionsLoading.value = false
  }
}

async function loadArchives() {
  loading.value = true
  try {
    const response = await fetchArchivesPage({
      keyword: filters.keyword || undefined,
      archive_code: filters.archive_code || undefined,
      year: filters.year || undefined,
      retention_period: filters.retention_period || undefined,
      security_level: filters.security_level || undefined,
      status: filters.status || undefined,
      responsible_dept_id: filters.responsible_dept_id || undefined,
      location_id: canManageArchives.value ? filters.location_id || undefined : undefined,
      page: archivePagination.current,
      page_size: archivePagination.pageSize,
    })
    archives.value = response.data.items
    archivePagination.total = response.data.pagination.total
    archivePagination.current = response.data.pagination.page
    archivePagination.pageSize = response.data.pagination.page_size
    selectedArchiveIds.value = selectedArchiveIds.value.filter((archiveId) =>
      response.data.items.some((archive) => archive.id === archiveId),
    )
  } catch (error) {
    handleRequestError(error, "加载档案检索结果失败。")
  } finally {
    loading.value = false
  }
}

async function openDetail(archiveId: number) {
  detailOpen.value = true
  detailLoading.value = true
  resetTransitionForm()
  try {
    const response = await fetchArchiveDetail(archiveId)
    selectedArchive.value = response.data
  } catch (error) {
    handleRequestError(error, "加载档案详情失败。")
  } finally {
    detailLoading.value = false
  }
}

function openEdit(archiveId: number) {
  void router.push(`/archives/records/${archiveId}/edit`)
}

function openPrintPage(archiveIds: number[]) {
  const resolvedArchiveIds = [...new Set(archiveIds)]
    .map((archiveId) => Number(archiveId))
    .filter((archiveId) => Number.isInteger(archiveId) && archiveId > 0)

  if (!resolvedArchiveIds.length) {
    message.warning("请先选择需要打印的档案。")
    return
  }

  const routeLocation = router.resolve({
    name: "archive-record-print",
    query: {
      archiveIds: resolvedArchiveIds.join(","),
    },
  })
  const printWindow = window.open(routeLocation.href, "_blank", "noopener")
  if (!printWindow) {
    void router.push(routeLocation.fullPath)
  }
}

function handleBatchPrint() {
  openPrintPage(selectedArchiveIds.value)
}

async function handleGenerateCodes(archiveId: number) {
  actionLoadingId.value = archiveId
  try {
    const response = await generateArchiveCodes(archiveId)
    message.success(response.message)
    if (selectedArchive.value?.id === archiveId) {
      selectedArchive.value = response.data
    }
  } catch (error) {
    handleRequestError(error, "生成档案条码失败。")
  } finally {
    actionLoadingId.value = null
  }
}

async function handleTransitionStatus() {
  if (!selectedArchive.value || !transitionForm.next_status) {
    message.warning("请先选择目标状态。")
    return
  }

  if (transitionForm.next_status === "BORROWED" && !transitionForm.current_borrow_id) {
    message.warning("流转到借出中时必须填写借阅单 ID。")
    return
  }

  transitionSubmitting.value = true
  try {
    const response = await transitionArchiveStatus(selectedArchive.value.id, {
      next_status: transitionForm.next_status,
      current_borrow_id: transitionForm.current_borrow_id,
      remark: transitionForm.remark || undefined,
    })
    selectedArchive.value = response.data
    resetTransitionForm()
    message.success(response.message)
    await loadArchives()
  } catch (error) {
    handleRequestError(error, "档案状态流转失败。")
  } finally {
    transitionSubmitting.value = false
  }
}

async function handleOpenFilePreview(file: ArchiveFile) {
  fileAccessLoadingId.value = file.id
  previewLoading.value = true
  try {
    const response = await createArchiveFilePreviewTicket(file.id)
    previewSource.value = buildArchiveAccessUrl(response.data.access_url)
    previewTitle.value = response.data.file_name
    previewWatermarkText.value = response.data.watermark_text
    previewFileExt.value = response.data.file_ext.toLowerCase()
    previewOpen.value = true
  } catch (error) {
    handleRequestError(error, "获取文件预览票据失败。")
  } finally {
    previewLoading.value = false
    fileAccessLoadingId.value = null
  }
}

function openDownloadModal(file: ArchiveFile) {
  selectedFileForAccess.value = file
  downloadPurpose.value = ""
  downloadOpen.value = true
}

async function handleDownloadFile() {
  if (!selectedFileForAccess.value) {
    return
  }
  if (!downloadPurpose.value.trim()) {
    message.warning("请填写下载用途。")
    return
  }

  fileAccessLoadingId.value = selectedFileForAccess.value.id
  downloadSubmitting.value = true
  try {
    const response = await createArchiveFileDownloadTicket(selectedFileForAccess.value.id, {
      purpose: downloadPurpose.value.trim(),
    })
    const link = document.createElement("a")
    link.href = buildArchiveAccessUrl(response.data.access_url)
    link.target = "_blank"
    link.rel = "noopener"
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    message.success("下载请求已提交，并已写入审计日志。")
    downloadOpen.value = false
    resetDownloadState()
  } catch (error) {
    handleRequestError(error, "申请文件下载失败。")
  } finally {
    downloadSubmitting.value = false
    fileAccessLoadingId.value = null
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
  void loadArchives()
  void loadFilterOptions()
})
</script>

<style scoped>
.archive-page {
  display: grid;
  gap: 20px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.summary-card {
  border-radius: 22px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(241, 248, 243, 0.92));
  box-shadow: 0 18px 40px rgba(16, 61, 49, 0.08);
}

.summary-card :deep(.ant-card-body) {
  display: grid;
  gap: 8px;
}

.summary-card span {
  color: #667085;
}

.summary-card strong {
  font-size: 30px;
  color: #0a7152;
}

.summary-card small {
  color: #667085;
  line-height: 1.7;
}

.panel-card {
  border-radius: 24px;
}

.toolbar-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.toolbar-search,
.toolbar-select,
.toolbar-input {
  width: 100%;
}

.toolbar-actions {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.selection-hint {
  color: #667085;
  font-size: 13px;
}

.title-cell,
.responsible-cell {
  display: grid;
  gap: 6px;
}

.title-cell span,
.responsible-cell span {
  color: #667085;
  font-size: 12px;
}

.detail-alert,
.file-alert {
  margin-bottom: 16px;
}

.detail-block {
  margin-top: 16px;
}

.transition-alert {
  margin-bottom: 16px;
}

.transition-form {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.transition-input {
  min-width: 180px;
}

.transition-remark {
  flex: 1;
}

.barcode-grid,
.file-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.barcode-card,
.file-card {
  display: grid;
  gap: 10px;
  padding: 16px;
  border: 1px solid rgba(10, 113, 82, 0.12);
  border-radius: 18px;
}

.barcode-image :deep(img),
.file-thumbnail :deep(img) {
  object-fit: contain;
}

.barcode-card small {
  color: #667085;
  font-size: 12px;
}

.file-card-header {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}

.file-meta {
  display: grid;
  gap: 4px;
  color: #667085;
  font-size: 12px;
}

.file-text {
  margin: 0;
  color: #475467;
  line-height: 1.7;
}

.preview-shell {
  position: relative;
  min-height: 580px;
  overflow: hidden;
  border-radius: 18px;
  background: #f4f7f5;
}

.preview-frame,
.preview-image {
  width: 100%;
  min-height: 580px;
  border: none;
}

.preview-image {
  object-fit: contain;
  background: #ffffff;
}

.preview-watermark {
  position: absolute;
  inset: 0;
  z-index: 2;
  pointer-events: none;
  background-repeat: repeat;
}

.revision-item {
  display: grid;
  gap: 4px;
}

.revision-item span,
.revision-item small {
  color: #667085;
}

@media (max-width: 960px) {
  .toolbar-actions {
    flex-direction: column;
  }

  .transition-form {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
