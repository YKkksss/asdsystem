<template>
  <section class="report-page">
    <div class="summary-grid">
      <a-card v-for="item in summaryCards" :key="item.label" :bordered="false" class="summary-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.caption }}</small>
      </a-card>
    </div>

    <a-card :bordered="false" class="panel-card">
      <div class="toolbar-grid">
        <a-input
          v-model:value="filters.start_date"
          class="toolbar-control"
          type="date"
          placeholder="开始日期"
        />
        <a-input
          v-model:value="filters.end_date"
          class="toolbar-control"
          type="date"
          placeholder="结束日期"
        />
        <a-select
          v-model:value="filters.applicant_dept_id"
          allow-clear
          class="toolbar-control"
          :options="departmentOptions"
          placeholder="申请部门"
          show-search
          option-filter-prop="label"
        />
        <a-select
          v-model:value="filters.archive_security_level"
          allow-clear
          class="toolbar-control"
          :options="securityOptions"
          placeholder="档案密级"
        />
        <a-select
          v-model:value="filters.archive_status"
          allow-clear
          class="toolbar-control"
          :options="archiveStatusOptions"
          placeholder="档案状态"
        />
        <a-input
          v-model:value="filters.carrier_type"
          class="toolbar-control"
          placeholder="载体类型，如纸质、电子"
        />
      </div>

      <div class="toolbar-actions">
        <a-space wrap>
          <a-button @click="handleReset">重置筛选</a-button>
          <a-button type="primary" :loading="loading" @click="loadPageData">刷新报表</a-button>
        </a-space>

        <a-space wrap>
          <a-button
            :loading="exportingType === 'departments'"
            @click="handleExport('departments')"
          >
            导出部门统计
          </a-button>
          <a-button
            type="primary"
            ghost
            :loading="exportingType === 'archives'"
            @click="handleExport('archives')"
          >
            导出档案排行
          </a-button>
        </a-space>
      </div>
    </a-card>

    <a-card :bordered="false" class="panel-card">
      <template #title>部门借阅排行</template>
      <a-table
        :columns="departmentColumns"
        :data-source="departmentRows"
        :loading="loading"
        row-key="applicant_dept_id"
        :pagination="{ pageSize: 8, showSizeChanger: false }"
      >
        <template #emptyText>
          <a-empty description="暂无部门借阅统计数据" />
        </template>

        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'applicant_dept_name'">
            <div class="dept-cell">
              <strong>{{ record.applicant_dept_name }}</strong>
              <span>部门 ID：{{ record.applicant_dept_id }}</span>
            </div>
          </template>

          <template v-else-if="column.key === 'overdue_rate'">
            <a-tag :color="record.overdue_rate > 0 ? 'orange' : 'green'">
              {{ record.overdue_rate }}%
            </a-tag>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-card :bordered="false" class="panel-card">
      <template #title>档案利用率排行</template>
      <a-table
        :columns="archiveColumns"
        :data-source="archiveRows"
        :loading="loading"
        row-key="archive_id"
        :pagination="{ pageSize: 8, showSizeChanger: false }"
      >
        <template #emptyText>
          <a-empty description="暂无档案利用率统计数据" />
        </template>

        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'archive'">
            <div class="archive-cell">
              <strong>{{ record.archive_title }}</strong>
              <span>{{ record.archive_code }}</span>
            </div>
          </template>

          <template v-else-if="column.key === 'security_level'">
            <a-tag color="gold">
              {{ securityLabelMap[record.security_level] || record.security_level }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'status'">
            <a-tag :color="archiveStatusColorMap[record.status] || 'default'">
              {{ archiveStatusLabelMap[record.status] || record.status }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'latest_borrowed_at'">
            {{ formatDateTime(record.latest_borrowed_at) }}
          </template>
        </template>
      </a-table>
    </a-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import { message } from "ant-design-vue"

import {
  exportReportCsv,
  fetchArchiveReports,
  fetchDepartmentReports,
  fetchReportSummary,
  type ArchiveUtilizationReportRow,
  type DepartmentReportRow,
  type ReportFilterParams,
  type ReportSummary,
} from "@/api/reports"
import { fetchDepartments } from "@/api/organizations"

const securityLabelMap: Record<string, string> = {
  PUBLIC: "公开",
  INTERNAL: "内部",
  SECRET: "秘密",
  CONFIDENTIAL: "机密",
  TOP_SECRET: "绝密",
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

const archiveStatusColorMap: Record<string, string> = {
  DRAFT: "default",
  PENDING_SCAN: "cyan",
  PENDING_CATALOG: "blue",
  ON_SHELF: "green",
  BORROWED: "orange",
  DESTROY_PENDING: "purple",
  DESTROYED: "red",
  FROZEN: "geekblue",
}

const securityOptions = Object.entries(securityLabelMap).map(([value, label]) => ({ value, label }))
const archiveStatusOptions = Object.entries(archiveStatusLabelMap).map(([value, label]) => ({ value, label }))

const departmentColumns = [
  { title: "申请部门", key: "applicant_dept_name" },
  { title: "借阅次数", key: "borrow_count", dataIndex: "borrow_count", width: 120 },
  { title: "超期次数", key: "overdue_count", dataIndex: "overdue_count", width: 120 },
  { title: "已归还", key: "returned_count", dataIndex: "returned_count", width: 120 },
  { title: "超期率", key: "overdue_rate", width: 120 },
]

const archiveColumns = [
  { title: "排行", key: "rank", dataIndex: "rank", width: 90 },
  { title: "档案", key: "archive" },
  { title: "密级", key: "security_level", width: 110 },
  { title: "状态", key: "status", width: 130 },
  { title: "载体", key: "carrier_type", dataIndex: "carrier_type", width: 120 },
  { title: "借阅次数", key: "borrow_count", dataIndex: "borrow_count", width: 120 },
  { title: "超期次数", key: "overdue_count", dataIndex: "overdue_count", width: 120 },
  { title: "已归还", key: "returned_count", dataIndex: "returned_count", width: 120 },
  { title: "最近借阅", key: "latest_borrowed_at", width: 180 },
]

const loading = ref(false)
const exportingType = ref<"departments" | "archives" | null>(null)
const departmentRows = ref<DepartmentReportRow[]>([])
const archiveRows = ref<ArchiveUtilizationReportRow[]>([])
const departmentOptions = ref<Array<{ value: number; label: string }>>([])

const summary = reactive<ReportSummary>({
  total_borrow_count: 0,
  overdue_count: 0,
  overdue_rate: 0,
  returned_count: 0,
  active_borrow_count: 0,
  total_archive_count: 0,
  utilized_archive_count: 0,
  archive_utilization_rate: 0,
})

const filters = reactive({
  start_date: "",
  end_date: "",
  applicant_dept_id: undefined as number | undefined,
  archive_security_level: undefined as string | undefined,
  archive_status: undefined as string | undefined,
  carrier_type: "",
})

const summaryCards = computed(() => [
  { label: "借阅总次数", value: summary.total_borrow_count, caption: "当前筛选范围内的借阅申请总量" },
  { label: "超期总次数", value: summary.overdue_count, caption: `超期率 ${summary.overdue_rate}%` },
  { label: "已归还数量", value: summary.returned_count, caption: "已完成归还闭环的借阅记录" },
  { label: "在借数量", value: summary.active_borrow_count, caption: "待审批、已审批、借出中和超期中的记录" },
  { label: "档案总量", value: summary.total_archive_count, caption: "当前筛选条件命中的档案总数" },
  { label: "利用档案数", value: summary.utilized_archive_count, caption: `利用率 ${summary.archive_utilization_rate}%` },
])

function buildQueryParams(): ReportFilterParams {
  return {
    start_date: filters.start_date || undefined,
    end_date: filters.end_date || undefined,
    applicant_dept_id: filters.applicant_dept_id,
    archive_security_level: filters.archive_security_level,
    archive_status: filters.archive_status,
    carrier_type: filters.carrier_type.trim() || undefined,
  }
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "-"
  }
  return value.replace("T", " ").slice(0, 19)
}

function handleReset() {
  filters.start_date = ""
  filters.end_date = ""
  filters.applicant_dept_id = undefined
  filters.archive_security_level = undefined
  filters.archive_status = undefined
  filters.carrier_type = ""
  void loadPageData()
}

async function loadFilterOptions() {
  const response = await fetchDepartments()
  departmentOptions.value = response.data
    .filter((item) => item.status)
    .map((item) => ({
      value: item.id,
      label: `${item.dept_name}（${item.dept_code}）`,
    }))
}

async function loadPageData() {
  loading.value = true
  try {
    const params = buildQueryParams()
    const [summaryResponse, departmentResponse, archiveResponse] = await Promise.all([
      fetchReportSummary(params),
      fetchDepartmentReports(params),
      fetchArchiveReports(params),
    ])

    summary.total_borrow_count = summaryResponse.data.total_borrow_count
    summary.overdue_count = summaryResponse.data.overdue_count
    summary.overdue_rate = summaryResponse.data.overdue_rate
    summary.returned_count = summaryResponse.data.returned_count
    summary.active_borrow_count = summaryResponse.data.active_borrow_count
    summary.total_archive_count = summaryResponse.data.total_archive_count
    summary.utilized_archive_count = summaryResponse.data.utilized_archive_count
    summary.archive_utilization_rate = summaryResponse.data.archive_utilization_rate
    departmentRows.value = departmentResponse.data
    archiveRows.value = archiveResponse.data
  } catch (error) {
    handleRequestError(error, "加载报表数据失败。")
  } finally {
    loading.value = false
  }
}

async function handleExport(reportType: "departments" | "archives") {
  exportingType.value = reportType
  try {
    const response = await exportReportCsv({
      ...buildQueryParams(),
      report_type: reportType,
    })
    const objectUrl = window.URL.createObjectURL(response.blob)
    const link = document.createElement("a")
    link.href = objectUrl
    link.download = response.fileName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(objectUrl)
    message.success("报表导出成功，系统已记录导出审计日志。")
  } catch (error) {
    handleRequestError(error, "导出报表失败。")
  } finally {
    exportingType.value = null
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
  void Promise.all([loadFilterOptions(), loadPageData()]).catch((error: unknown) => {
    handleRequestError(error, "初始化报表页面失败。")
  })
})
</script>

<style scoped>
.report-page {
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

.summary-card {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(241, 248, 243, 0.9));
  box-shadow: 0 18px 40px rgba(16, 61, 49, 0.08);
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
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.toolbar-control {
  width: 100%;
}

.toolbar-actions {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-top: 16px;
}

.dept-cell,
.archive-cell {
  display: grid;
  gap: 4px;
}

.dept-cell span,
.archive-cell span {
  color: #667085;
}

@media (max-width: 1200px) {
  .toolbar-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 960px) {
  .toolbar-grid {
    grid-template-columns: 1fr;
  }

  .toolbar-actions {
    flex-direction: column;
  }
}
</style>
