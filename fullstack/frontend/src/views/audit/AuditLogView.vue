<template>
  <section class="audit-page">
    <div class="summary-grid">
      <a-card :bordered="false" class="summary-card">
        <span>日志总数</span>
        <strong>{{ summary.total_count }}</strong>
        <small>当前系统已记录的关键操作审计总数</small>
      </a-card>
      <a-card :bordered="false" class="summary-card">
        <span>今日新增</span>
        <strong>{{ summary.today_count }}</strong>
        <small>今天新增的审计日志数量</small>
      </a-card>
      <a-card :bordered="false" class="summary-card">
        <span>异常结果</span>
        <strong>{{ summary.failed_count }}</strong>
        <small>失败与拒绝类操作累计数量</small>
      </a-card>
      <a-card :bordered="false" class="summary-card">
        <span>文件风控</span>
        <strong>{{ summary.preview_count + summary.download_count }}</strong>
        <small>预览与下载相关审计次数</small>
      </a-card>
    </div>

    <a-card :bordered="false" class="panel-card">
      <div class="toolbar-grid">
        <a-input-search
          v-model:value="filters.keyword"
          allow-clear
          placeholder="按用户、目标摘要或描述搜索"
          @search="loadPageData"
        />
        <a-select
          v-model:value="filters.module_name"
          allow-clear
          class="toolbar-select"
          :options="moduleOptions"
          placeholder="模块"
        />
        <a-select
          v-model:value="filters.result_status"
          allow-clear
          class="toolbar-select"
          :options="resultOptions"
          placeholder="结果"
        />
      </div>

      <div class="toolbar-actions">
        <a-space wrap>
          <a-button @click="handleReset">重置筛选</a-button>
          <a-button type="primary" :loading="loading" @click="loadPageData">刷新日志</a-button>
        </a-space>

        <div class="module-tags">
          <a-tag v-for="item in summary.module_counts" :key="item.module_name" color="processing">
            {{ moduleLabelMap[item.module_name] || item.module_name }} {{ item.count }}
          </a-tag>
        </div>
      </div>

      <a-table
        :columns="columns"
        :data-source="logs"
        :loading="loading"
        row-key="id"
        :pagination="{ pageSize: 10, showSizeChanger: false }"
      >
        <template #emptyText>
          <a-empty description="暂无审计日志" />
        </template>

        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'user'">
            <div class="user-cell">
              <strong>{{ record.real_name || "系统" }}</strong>
              <span>{{ record.username || "-" }}</span>
            </div>
          </template>

          <template v-else-if="column.key === 'module_name'">
            <a-tag color="blue">{{ moduleLabelMap[record.module_name] || record.module_name }}</a-tag>
          </template>

          <template v-else-if="column.key === 'result_status'">
            <a-tag :color="resultColorMap[record.result_status] || 'default'">
              {{ resultLabelMap[record.result_status] || record.result_status }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'description'">
            <div class="description-cell">
              <strong>{{ actionLabelMap[record.action_code] || record.action_code }}</strong>
              <span>{{ record.description }}</span>
              <small>{{ record.target_repr || "无目标摘要" }}</small>
            </div>
          </template>

          <template v-else-if="column.key === 'created_at'">
            {{ formatDateTime(record.created_at) }}
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-button type="link" @click="openDetail(record)">查看详情</a-button>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-drawer
      v-model:open="detailOpen"
      title="审计日志详情"
      :width="720"
      destroy-on-close
    >
      <template v-if="selectedLog">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="操作时间">{{ formatDateTime(selectedLog.created_at) }}</a-descriptions-item>
          <a-descriptions-item label="业务模块">
            {{ moduleLabelMap[selectedLog.module_name] || selectedLog.module_name }}
          </a-descriptions-item>
          <a-descriptions-item label="动作编码">{{ selectedLog.action_code }}</a-descriptions-item>
          <a-descriptions-item label="结果">
            {{ resultLabelMap[selectedLog.result_status] || selectedLog.result_status }}
          </a-descriptions-item>
          <a-descriptions-item label="操作用户">
            {{ selectedLog.real_name || "系统" }} / {{ selectedLog.username || "-" }}
          </a-descriptions-item>
          <a-descriptions-item label="目标对象">{{ selectedLog.target_repr || "-" }}</a-descriptions-item>
          <a-descriptions-item label="业务类型">{{ selectedLog.biz_type || "-" }}</a-descriptions-item>
          <a-descriptions-item label="业务 ID">{{ selectedLog.biz_id || "-" }}</a-descriptions-item>
          <a-descriptions-item label="请求方式">{{ selectedLog.request_method || "-" }}</a-descriptions-item>
          <a-descriptions-item label="请求路径">{{ selectedLog.request_path || "-" }}</a-descriptions-item>
          <a-descriptions-item label="来源 IP">{{ selectedLog.ip_address || "-" }}</a-descriptions-item>
          <a-descriptions-item label="用户代理">{{ selectedLog.user_agent || "-" }}</a-descriptions-item>
          <a-descriptions-item label="审计描述">{{ selectedLog.description }}</a-descriptions-item>
        </a-descriptions>

        <div class="detail-section">
          <strong>扩展上下文</strong>
          <pre class="extra-json">{{ formatExtraData(selectedLog.extra_data_json) }}</pre>
        </div>
      </template>
    </a-drawer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue"
import { message } from "ant-design-vue"

import { fetchAuditLogs, fetchAuditSummary, type AuditLog, type AuditSummary } from "@/api/audit"

const moduleLabelMap: Record<string, string> = {
  AUTH: "登录认证",
  ARCHIVES: "档案管理",
  DIGITIZATION: "数字化",
  BORROWING: "借阅管理",
  DESTRUCTION: "销毁管理",
}

const resultLabelMap: Record<string, string> = {
  SUCCESS: "成功",
  FAILED: "失败",
  DENIED: "拒绝",
}

const resultColorMap: Record<string, string> = {
  SUCCESS: "green",
  FAILED: "red",
  DENIED: "orange",
}

const actionLabelMap: Record<string, string> = {
  LOGIN_SUCCESS: "登录成功",
  LOGIN_FAILED: "登录失败",
  LOGIN_LOCKED: "登录锁定",
  USER_UNLOCK: "账号解锁",
  ARCHIVE_CREATE: "创建档案",
  ARCHIVE_UPDATE: "更新档案",
  ARCHIVE_STATUS_TRANSITION: "档案状态流转",
  ARCHIVE_CODE_GENERATE: "生成条码二维码",
  ARCHIVE_FILE_PREVIEW_APPLY: "申请预览票据",
  ARCHIVE_FILE_PREVIEW_ACCESS: "访问预览内容",
  ARCHIVE_FILE_DOWNLOAD_APPLY: "申请下载票据",
  ARCHIVE_FILE_DOWNLOAD_ACCESS: "下载文件内容",
  SCAN_TASK_CREATE: "创建扫描任务",
  SCAN_TASK_FILE_UPLOAD: "上传扫描文件",
  BORROW_APPLICATION_CREATE: "创建借阅申请",
  BORROW_APPLICATION_APPROVE: "借阅审批",
  BORROW_CHECKOUT: "借阅出库",
  BORROW_RETURN_SUBMIT: "提交归还",
  BORROW_RETURN_CONFIRM: "归还确认",
  BORROW_REMINDER_DISPATCH: "催还扫描",
  DESTROY_APPLICATION_CREATE: "创建销毁申请",
  DESTROY_APPLICATION_APPROVE: "销毁审批",
  DESTROY_EXECUTE: "执行销毁",
}

const moduleOptions = Object.entries(moduleLabelMap).map(([value, label]) => ({ value, label }))
const resultOptions = Object.entries(resultLabelMap).map(([value, label]) => ({ value, label }))

const columns = [
  { title: "操作时间", key: "created_at", width: 180 },
  { title: "操作用户", key: "user", width: 140 },
  { title: "业务模块", key: "module_name", width: 120 },
  { title: "审计内容", key: "description" },
  { title: "结果", key: "result_status", width: 110 },
  { title: "操作", key: "actions", width: 120 },
]

const loading = ref(false)
const logs = ref<AuditLog[]>([])
const detailOpen = ref(false)
const selectedLog = ref<AuditLog | null>(null)
const summary = reactive<AuditSummary>({
  total_count: 0,
  today_count: 0,
  failed_count: 0,
  preview_count: 0,
  download_count: 0,
  module_counts: [],
})

const filters = reactive({
  keyword: "",
  module_name: undefined as string | undefined,
  result_status: undefined as string | undefined,
})

function formatDateTime(value: string | null) {
  if (!value) {
    return "-"
  }
  return value.replace("T", " ").slice(0, 19)
}

function formatExtraData(value: Record<string, unknown>) {
  const keys = Object.keys(value || {})
  if (!keys.length) {
    return "无扩展上下文"
  }
  return JSON.stringify(value, null, 2)
}

function openDetail(log: AuditLog) {
  selectedLog.value = log
  detailOpen.value = true
}

function handleReset() {
  filters.keyword = ""
  filters.module_name = undefined
  filters.result_status = undefined
  void loadPageData()
}

async function loadPageData() {
  loading.value = true
  try {
    const [logsResponse, summaryResponse] = await Promise.all([
      fetchAuditLogs({
        keyword: filters.keyword.trim() || undefined,
        module_name: filters.module_name,
        result_status: filters.result_status,
      }),
      fetchAuditSummary(),
    ])
    logs.value = logsResponse.data
    summary.total_count = summaryResponse.data.total_count
    summary.today_count = summaryResponse.data.today_count
    summary.failed_count = summaryResponse.data.failed_count
    summary.preview_count = summaryResponse.data.preview_count
    summary.download_count = summaryResponse.data.download_count
    summary.module_counts = summaryResponse.data.module_counts
  } catch (error) {
    handleRequestError(error, "加载审计日志失败。")
  } finally {
    loading.value = false
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
  void loadPageData()
})
</script>

<style scoped>
.audit-page {
  display: grid;
  gap: 20px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
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
  grid-template-columns: minmax(0, 1.4fr) 180px 180px;
  gap: 12px;
}

.toolbar-select {
  width: 100%;
}

.toolbar-actions {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin: 16px 0;
}

.module-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.detail-section {
  margin-top: 16px;
  display: grid;
  gap: 12px;
}

.extra-json {
  margin: 0;
  padding: 16px;
  border-radius: 16px;
  background: #0f172a;
  color: #e2e8f0;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.user-cell,
.description-cell {
  display: grid;
  gap: 4px;
}

.user-cell span,
.description-cell span,
.description-cell small {
  color: #667085;
}

@media (max-width: 960px) {
  .toolbar-grid {
    grid-template-columns: 1fr;
  }

  .toolbar-actions {
    flex-direction: column;
  }

  .module-tags {
    justify-content: flex-start;
  }
}
</style>
