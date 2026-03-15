<template>
  <section class="borrow-page">
    <div class="summary-grid">
      <a-card v-for="item in summaryCards" :key="item.label" :bordered="false" class="summary-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.caption }}</small>
      </a-card>
    </div>

    <a-row :gutter="[20, 20]">
      <a-col :xs="24" :xl="15">
        <a-card :bordered="false" class="panel-card">
          <div class="toolbar-grid">
            <a-input-search
              v-model:value="filters.keyword"
              allow-clear
              placeholder="按申请编号、档号、题名或用途搜索"
              @search="handleApplyFilters"
            />

            <a-select
              v-if="canViewAllApplications"
              v-model:value="filters.scope"
              class="toolbar-select"
              :options="scopeOptions"
            />

            <a-select
              v-model:value="filters.status"
              allow-clear
              class="toolbar-select"
              placeholder="筛选借阅状态"
              :options="statusOptions"
            />
          </div>

          <div class="toolbar-actions">
            <a-space wrap>
              <a-button @click="handleResetFilters">重置筛选</a-button>
              <a-button type="primary" @click="loadApplications">刷新列表</a-button>
            </a-space>
          </div>

          <a-table
            :columns="columns"
            :data-source="applications"
            :loading="loading"
            row-key="id"
            :pagination="{
              current: applicationPagination.current,
              pageSize: applicationPagination.pageSize,
              total: applicationPagination.total,
              showSizeChanger: true,
              pageSizeOptions: ['8', '20', '50'],
              onChange: handleApplicationTableChange,
              onShowSizeChange: handleApplicationTableChange,
              showTotal: (total: number) => `共 ${total} 条`,
            }"
          >
            <template #emptyText>
              <a-empty description="暂无借阅申请记录" />
            </template>

            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'archive'">
                <div class="archive-cell">
                  <strong>{{ record.archive_title }}</strong>
                  <span>{{ record.archive_code }}</span>
                </div>
              </template>

              <template v-else-if="column.key === 'status'">
                <a-tag :color="statusColorMap[record.status] || 'default'">
                  {{ statusLabelMap[record.status] || record.status }}
                </a-tag>
              </template>

              <template v-else-if="column.key === 'expected_return_at'">
                <span>{{ formatDateTime(record.expected_return_at) }}</span>
              </template>

              <template v-else-if="column.key === 'actions'">
                <a-space wrap>
                  <a-button type="link" @click="openDetail(record.id)">查看详情</a-button>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>

      <a-col :xs="24" :xl="9">
        <a-card :bordered="false" class="panel-card">
          <template #title>新建借阅申请</template>

          <a-alert
            class="form-alert"
            show-icon
            type="info"
            message="一张借阅申请只对应一份档案，提交后将自动流转到所属部门审批负责人。"
          />

          <a-form :model="formState" layout="vertical" @finish="handleCreateApplication">
            <a-form-item label="档案选择" name="archive_id" :rules="requiredRules">
              <a-select
                v-model:value="formState.archive_id"
                :loading="optionsLoading"
                :options="archiveOptions"
                placeholder="选择已上架档案"
                show-search
                :filter-option="filterOption"
              />
            </a-form-item>

            <a-form-item label="借阅用途" name="purpose" :rules="requiredRules">
              <a-textarea
                v-model:value="formState.purpose"
                :rows="4"
                placeholder="请填写借阅用途、使用场景和时限说明"
              />
            </a-form-item>

            <a-form-item label="预计归还时间" name="expected_return_at" :rules="requiredRules">
              <a-date-picker
                v-model:value="formState.expected_return_at"
                class="full-width"
                show-time
                value-format="YYYY-MM-DDTHH:mm:ssZ"
                placeholder="请选择预计归还时间"
              />
            </a-form-item>

            <div class="form-actions">
              <a-button @click="handleResetForm">重置</a-button>
              <a-button html-type="submit" type="primary" :loading="submitting">提交申请</a-button>
            </div>
          </a-form>
        </a-card>
      </a-col>
    </a-row>

    <a-drawer v-model:open="detailOpen" :width="720" title="借阅申请详情">
      <a-spin :spinning="detailLoading">
        <template v-if="selectedApplication">
          <a-descriptions :column="2" bordered size="small">
            <a-descriptions-item label="申请编号">{{ selectedApplication.application_no }}</a-descriptions-item>
            <a-descriptions-item label="当前状态">
              {{ statusLabelMap[selectedApplication.status] || selectedApplication.status }}
            </a-descriptions-item>
            <a-descriptions-item label="档号">{{ selectedApplication.archive_code }}</a-descriptions-item>
            <a-descriptions-item label="题名">{{ selectedApplication.archive_title }}</a-descriptions-item>
            <a-descriptions-item label="申请人">{{ selectedApplication.applicant_name }}</a-descriptions-item>
            <a-descriptions-item label="所属部门">{{ selectedApplication.applicant_dept_name }}</a-descriptions-item>
            <a-descriptions-item label="当前审批人">
              {{ selectedApplication.current_approver_name || "已完成当前审批环节" }}
            </a-descriptions-item>
            <a-descriptions-item label="预计归还时间">
              {{ formatDateTime(selectedApplication.expected_return_at) }}
            </a-descriptions-item>
            <a-descriptions-item :span="2" label="借阅用途">
              {{ selectedApplication.purpose }}
            </a-descriptions-item>
            <a-descriptions-item v-if="selectedApplication.reject_reason" :span="2" label="驳回原因">
              {{ selectedApplication.reject_reason }}
            </a-descriptions-item>
          </a-descriptions>

          <a-card class="detail-block" size="small" title="审批记录">
            <a-timeline v-if="selectedApplication.approval_records.length">
              <a-timeline-item v-for="item in selectedApplication.approval_records" :key="item.id">
                <div class="timeline-item">
                  <strong>{{ item.approver_name }}</strong>
                  <span>{{ item.action === "APPROVE" ? "审批通过" : "审批驳回" }}</span>
                  <small>{{ formatDateTime(item.approved_at) }}</small>
                  <p>{{ item.opinion || "未填写审批意见" }}</p>
                </div>
              </a-timeline-item>
            </a-timeline>
            <a-empty v-else description="尚无审批记录" />
          </a-card>

          <a-card class="detail-block" size="small" title="出库记录">
            <template v-if="selectedApplication.checkout_record">
              <a-descriptions :column="2" bordered size="small">
                <a-descriptions-item label="领取人">
                  {{ selectedApplication.checkout_record.borrower_name }}
                </a-descriptions-item>
                <a-descriptions-item label="办理档案员">
                  {{ selectedApplication.checkout_record.operator_name }}
                </a-descriptions-item>
                <a-descriptions-item label="出库时间">
                  {{ formatDateTime(selectedApplication.checkout_record.checkout_at) }}
                </a-descriptions-item>
                <a-descriptions-item label="位置快照">
                  {{ selectedApplication.checkout_record.location_snapshot || "未记录" }}
                </a-descriptions-item>
                <a-descriptions-item :span="2" label="出库备注">
                  {{ selectedApplication.checkout_record.checkout_note || "未填写" }}
                </a-descriptions-item>
              </a-descriptions>
            </template>
            <a-empty v-else description="尚未办理出库" />
          </a-card>

          <a-card class="detail-block" size="small" title="归还记录">
            <template v-if="selectedApplication.return_record">
              <a-descriptions :column="2" bordered size="small">
                <a-descriptions-item label="归还提交人">
                  {{ selectedApplication.return_record.returned_by_user_name }}
                </a-descriptions-item>
                <a-descriptions-item label="归还状态">
                  {{ returnStatusLabelMap[selectedApplication.return_record.return_status] }}
                </a-descriptions-item>
                <a-descriptions-item label="提交时间">
                  {{ formatDateTime(selectedApplication.return_record.returned_at) }}
                </a-descriptions-item>
                <a-descriptions-item label="确认时间">
                  {{ formatDateTime(selectedApplication.return_record.confirmed_at) }}
                </a-descriptions-item>
                <a-descriptions-item :span="2" label="交接说明">
                  {{ selectedApplication.return_record.handover_note || "未填写" }}
                </a-descriptions-item>
              </a-descriptions>

              <div class="attachment-list">
                <a
                  v-for="item in selectedApplication.return_record.attachments"
                  :key="item.id"
                  :href="buildBorrowAttachmentUrl(item.file_path)"
                  class="attachment-link"
                  target="_blank"
                  rel="noreferrer"
                >
                  {{ item.file_name }}
                </a>
              </div>
            </template>
            <a-empty v-else description="尚未提交归还" />
          </a-card>
        </template>
      </a-spin>
    </a-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue"
import { message } from "ant-design-vue"
import type { SelectProps } from "ant-design-vue"
import { useRoute, useRouter } from "vue-router"

import { fetchArchives } from "@/api/archives"
import {
  buildBorrowAttachmentUrl,
  createBorrowApplication,
  fetchBorrowApplicationDetail,
  fetchBorrowApplications,
  fetchBorrowApplicationsPage,
  type BorrowApplication,
  type BorrowApplicationDetail,
} from "@/api/borrowing"
import { useAuthStore } from "@/stores/auth"
import { getRequestErrorMessage, getRequestErrorStatus } from "@/utils/request"

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const statusLabelMap: Record<string, string> = {
  DRAFT: "草稿",
  PENDING_APPROVAL: "待审批",
  APPROVED: "已通过",
  REJECTED: "已驳回",
  WITHDRAWN: "已撤回",
  CHECKED_OUT: "借出中",
  OVERDUE: "已超期",
  RETURNED: "已归还",
}

const returnStatusLabelMap: Record<string, string> = {
  SUBMITTED: "已提交归还",
  CONFIRMED: "已确认入库",
  REJECTED: "归还验收不通过",
}

const statusColorMap: Record<string, string> = {
  DRAFT: "default",
  PENDING_APPROVAL: "processing",
  APPROVED: "blue",
  REJECTED: "red",
  WITHDRAWN: "default",
  CHECKED_OUT: "gold",
  OVERDUE: "volcano",
  RETURNED: "green",
}

const canViewAllApplications = computed(() =>
  Boolean(authStore.profile?.roles.some((role) => ["ADMIN", "ARCHIVIST", "AUDITOR"].includes(role.role_code))),
)

const loading = ref(false)
const optionsLoading = ref(false)
const submitting = ref(false)
const detailLoading = ref(false)
const detailOpen = ref(false)
const applications = ref<BorrowApplication[]>([])
const selectedApplication = ref<BorrowApplicationDetail | null>(null)
const archiveOptions = ref<SelectProps["options"]>([])
const applicationPagination = reactive({
  current: 1,
  pageSize: 8,
  total: 0,
})

const requiredRules = [{ required: true, message: "该字段不能为空。" }]
const columns = [
  { title: "档案信息", key: "archive" },
  { title: "申请人", dataIndex: "applicant_name", key: "applicant_name", width: 120 },
  { title: "状态", key: "status", width: 120 },
  { title: "预计归还", key: "expected_return_at", width: 180 },
  { title: "当前审批人", dataIndex: "current_approver_name", key: "current_approver_name", width: 140 },
  { title: "操作", key: "actions", width: 120 },
]

const scopeOptions = [
  { label: "我的申请", value: "mine" },
  { label: "全部申请", value: "all" },
]

const statusOptions = Object.entries(statusLabelMap).map(([value, label]) => ({ value, label }))

const filters = reactive({
  keyword: "",
  status: undefined as string | undefined,
  scope: "mine" as "mine" | "all",
})

const initialFormState = () => ({
  archive_id: undefined as number | undefined,
  purpose: "",
  expected_return_at: "",
})

const formState = reactive(initialFormState())

const summaryCards = computed(() => {
  const total = applicationPagination.total
  const pending = applications.value.filter((item) => item.status === "PENDING_APPROVAL").length
  const checkedOut = applications.value.filter((item) => ["CHECKED_OUT", "OVERDUE"].includes(item.status)).length
  const returned = applications.value.filter((item) => item.status === "RETURNED").length
  return [
    { label: "申请总数", value: total, caption: "当前筛选条件下的借阅申请数量" },
    { label: "待审批", value: pending, caption: "仍在流转中的审批单据" },
    { label: "借出中", value: checkedOut, caption: "已经出库但尚未完成归还确认" },
    { label: "已归还", value: returned, caption: "流程已闭环的申请数量" },
  ]
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

function handleResetForm() {
  Object.assign(formState, initialFormState())
}

function handleResetFilters() {
  filters.keyword = ""
  filters.status = undefined
  filters.scope = "mine"
  applicationPagination.current = 1
  void loadApplications()
}

function handleApplyFilters() {
  applicationPagination.current = 1
  void loadApplications()
}

function handleApplicationTableChange(page: number, pageSize: number) {
  applicationPagination.current = page
  applicationPagination.pageSize = pageSize
  void loadApplications()
}

async function loadArchiveOptions() {
  optionsLoading.value = true
  try {
    const response = await fetchArchives({ status: "ON_SHELF" })
    archiveOptions.value = response.data.map((item) => ({
      value: item.id,
      label: `${item.archive_code}｜${item.title}｜${item.security_level}`,
    }))
  } catch (error) {
    handleRequestError(error, "加载可借阅档案失败。")
  } finally {
    optionsLoading.value = false
  }
}

async function loadApplications() {
  loading.value = true
  try {
    const response = await fetchBorrowApplicationsPage({
      scope: canViewAllApplications.value ? filters.scope : "mine",
      keyword: filters.keyword.trim() || undefined,
      status: filters.status,
      page: applicationPagination.current,
      page_size: applicationPagination.pageSize,
    })
    applications.value = response.data.items
    applicationPagination.total = response.data.pagination.total
    applicationPagination.current = response.data.pagination.page
    applicationPagination.pageSize = response.data.pagination.page_size
  } catch (error) {
    handleRequestError(error, "加载借阅申请失败。")
  } finally {
    loading.value = false
  }
}

async function openDetail(applicationId: number) {
  detailOpen.value = true
  detailLoading.value = true
  selectedApplication.value = null
  try {
    const response = await fetchBorrowApplicationDetail(applicationId)
    selectedApplication.value = response.data
  } catch (error) {
    detailOpen.value = false
    const status = getRequestErrorStatus(error)
    if (status === 404) {
      message.error("借阅申请不存在或已被删除，请刷新列表后重试。")
      await loadApplications()
      return
    }
    if (status === 403) {
      message.error("当前账号无权查看该借阅申请详情。")
      return
    }
    handleRequestError(error, "加载借阅申请详情失败。")
  } finally {
    detailLoading.value = false
  }
}

async function consumeRouteApplicationId() {
  const rawApplicationId = route.query.applicationId
  const applicationId = Number(rawApplicationId)
  if (!Number.isInteger(applicationId) || applicationId <= 0) {
    return
  }

  await openDetail(applicationId)
  const nextQuery = { ...route.query }
  delete nextQuery.applicationId
  await router.replace({ query: nextQuery })
}

async function handleCreateApplication() {
  submitting.value = true
  try {
    const response = await createBorrowApplication({
      archive_id: Number(formState.archive_id),
      purpose: formState.purpose.trim(),
      expected_return_at: formState.expected_return_at,
    })
    message.success(response.message)
    handleResetForm()
    await loadApplications()
    await loadArchiveOptions()
    await openDetail(response.data.id)
  } catch (error) {
    handleRequestError(error, "提交借阅申请失败。")
  } finally {
    submitting.value = false
  }
}

function handleRequestError(error: unknown, fallbackMessage: string) {
  message.error(getRequestErrorMessage(error, fallbackMessage))
}

onMounted(() => {
  void loadApplications()
  void loadArchiveOptions()
})

watch(
  () => route.query.applicationId,
  () => {
    void consumeRouteApplicationId()
  },
  { immediate: true },
)
</script>

<style scoped>
.borrow-page {
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

.summary-card span,
.summary-card small {
  color: #475467;
}

.summary-card strong {
  display: block;
  margin: 12px 0 6px;
  font-size: 26px;
}

.toolbar-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.toolbar-select,
.full-width {
  width: 100%;
}

.toolbar-actions {
  display: flex;
  justify-content: flex-end;
  margin: 16px 0;
}

.archive-cell {
  display: grid;
  gap: 4px;
}

.archive-cell span {
  color: #667085;
  font-size: 12px;
}

.form-alert {
  margin-bottom: 16px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.detail-block {
  margin-top: 16px;
}

.timeline-item {
  display: grid;
  gap: 6px;
}

.timeline-item span,
.timeline-item small,
.timeline-item p {
  color: #475467;
}

.timeline-item p {
  margin: 0;
}

.attachment-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 16px;
}

.attachment-link {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(10, 113, 82, 0.08);
  color: #0a7152;
}

@media (max-width: 960px) {
  .toolbar-actions {
    justify-content: flex-start;
  }

  .form-actions {
    justify-content: stretch;
  }
}
</style>
