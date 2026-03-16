<template>
  <section class="destruction-page">
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
          placeholder="按申请编号、档号、题名或申请人搜索"
          @search="handleApplyFilters"
        />
        <a-select
          v-model:value="filters.scope"
          class="toolbar-select"
          :options="scopeOptions"
          placeholder="查看范围"
        />
        <a-select
          v-model:value="filters.status"
          allow-clear
          class="toolbar-select"
          :options="statusOptions"
          placeholder="销毁状态"
        />
      </div>

      <div class="toolbar-actions">
        <a-space wrap>
          <a-button @click="handleReset">重置筛选</a-button>
          <a-button type="primary" :loading="loading" @click="loadApplications">刷新列表</a-button>
        </a-space>

        <a-button v-if="canCreateDestruction" type="primary" @click="openCreateModal">
          发起销毁申请
        </a-button>
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
          <a-empty description="当前没有销毁申请记录" />
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

          <template v-else-if="column.key === 'submitted_at'">
            {{ formatDateTime(record.submitted_at) }}
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-space wrap>
              <a-button type="link" @click="openDetailDrawer(record.id)">查看详情</a-button>
              <a-button
                v-if="record.can_approve && canApprove"
                type="link"
                @click="openApprovalModal(record)"
              >
                审批
              </a-button>
              <a-button
                v-if="record.can_execute && canExecuteDestruction"
                type="link"
                @click="openExecuteModal(record)"
              >
                执行销毁
              </a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-modal
      v-model:open="createModalOpen"
      :confirm-loading="createSubmitting"
      title="发起销毁申请"
      ok-text="提交申请"
      @ok="handleCreateApplication"
    >
      <a-form layout="vertical">
        <a-form-item label="选择档案" required>
          <a-select
            v-model:value="createForm.archive_id"
            show-search
            :loading="archiveLoading"
            placeholder="请选择已上架档案"
            :options="archiveOptions"
            option-filter-prop="label"
          />
        </a-form-item>
        <a-form-item label="销毁原因" required>
          <a-textarea
            v-model:value="createForm.reason"
            :rows="4"
            placeholder="例如：保管期限届满且无继续保存价值"
          />
        </a-form-item>
        <a-form-item label="销毁依据" required>
          <a-textarea
            v-model:value="createForm.basis"
            :rows="4"
            placeholder="请填写制度条款、审签依据或业务规定"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="approvalModalOpen"
      :confirm-loading="approvalSubmitting"
      title="处理销毁审批"
      ok-text="提交审批"
      @ok="handleSubmitApproval"
    >
      <template v-if="selectedApplication">
        <a-alert
          show-icon
          type="info"
          class="modal-alert"
          :message="`当前处理单号：${selectedApplication.application_no}`"
        />
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="档案">{{ selectedApplication.archive_title }}</a-descriptions-item>
          <a-descriptions-item label="申请人">{{ selectedApplication.applicant_name }}</a-descriptions-item>
          <a-descriptions-item label="销毁原因">{{ selectedApplication.reason }}</a-descriptions-item>
          <a-descriptions-item label="销毁依据">{{ selectedApplication.basis }}</a-descriptions-item>
        </a-descriptions>

        <a-form layout="vertical" class="modal-form">
          <a-form-item label="审批动作" required>
            <a-radio-group v-model:value="approvalForm.action">
              <a-radio value="APPROVE">审批通过</a-radio>
              <a-radio value="REJECT">驳回申请</a-radio>
            </a-radio-group>
          </a-form-item>
          <a-form-item :label="approvalForm.action === 'APPROVE' ? '审批意见' : '驳回原因'">
            <a-textarea
              v-model:value="approvalForm.opinion"
              :rows="4"
              :placeholder="approvalForm.action === 'APPROVE' ? '可补充审批说明' : '驳回时必须填写原因'"
            />
          </a-form-item>
        </a-form>
      </template>
    </a-modal>

    <a-modal
      v-model:open="executeModalOpen"
      :confirm-loading="executeSubmitting"
      title="执行档案销毁"
      ok-text="确认执行"
      @ok="handleSubmitExecution"
    >
      <template v-if="selectedApplication">
        <a-alert
          show-icon
          type="warning"
          class="modal-alert"
          :message="`执行后档案状态将流转为“已销毁”：${selectedApplication.archive_title}`"
        />
        <a-alert
          show-icon
          type="info"
          class="modal-alert"
          :message="`销毁附件支持 PDF、JPG、JPEG、PNG，单个文件不超过 ${destroyAttachmentMaxSizeMb} MB。`"
        />
        <a-form layout="vertical">
          <a-form-item label="执行说明" required>
            <a-textarea
              v-model:value="executionForm.execution_note"
              :rows="4"
              placeholder="请填写执行方式、现场情况和台账登记说明"
            />
          </a-form-item>
          <a-form-item label="销毁附件">
            <input
              ref="executionInputRef"
              class="upload-input"
              multiple
              type="file"
              :accept="destroyAttachmentAccept"
              @change="handleExecutionFileChange"
            />
            <a-button class="upload-button" @click="executionInputRef?.click()">选择附件</a-button>
            <div v-if="executionFiles.length" class="file-list">
              <span v-for="file in executionFiles" :key="file.name">{{ file.name }}</span>
            </div>
          </a-form-item>
        </a-form>
      </template>
    </a-modal>

    <a-drawer
      v-model:open="detailDrawerOpen"
      title="销毁申请详情"
      :width="760"
      destroy-on-close
    >
      <template v-if="detailLoading">
        <a-skeleton active :paragraph="{ rows: 8 }" />
      </template>
      <template v-else-if="detailRecord">
        <div class="detail-section">
          <a-descriptions :column="1" bordered size="small">
            <a-descriptions-item label="申请编号">{{ detailRecord.application_no }}</a-descriptions-item>
            <a-descriptions-item label="档案">{{ detailRecord.archive_title }}</a-descriptions-item>
            <a-descriptions-item label="档号">{{ detailRecord.archive_code }}</a-descriptions-item>
            <a-descriptions-item label="申请人">{{ detailRecord.applicant_name }}</a-descriptions-item>
            <a-descriptions-item label="申请部门">{{ detailRecord.applicant_dept_name }}</a-descriptions-item>
            <a-descriptions-item label="状态">
              <a-tag :color="statusColorMap[detailRecord.status] || 'default'">
                {{ statusLabelMap[detailRecord.status] || detailRecord.status }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item label="销毁原因">{{ detailRecord.reason }}</a-descriptions-item>
            <a-descriptions-item label="销毁依据">{{ detailRecord.basis }}</a-descriptions-item>
            <a-descriptions-item label="提交时间">{{ formatDateTime(detailRecord.submitted_at) }}</a-descriptions-item>
            <a-descriptions-item label="审批通过时间">{{ formatDateTime(detailRecord.approved_at) }}</a-descriptions-item>
            <a-descriptions-item label="驳回时间">{{ formatDateTime(detailRecord.rejected_at) }}</a-descriptions-item>
            <a-descriptions-item label="执行时间">{{ formatDateTime(detailRecord.executed_at) }}</a-descriptions-item>
            <a-descriptions-item label="驳回原因">{{ detailRecord.reject_reason || "-" }}</a-descriptions-item>
          </a-descriptions>
        </div>

        <div class="detail-section">
          <div class="section-head">
            <strong>审批记录</strong>
          </div>
          <a-empty v-if="!detailRecord.approval_records.length" description="暂无审批记录" />
          <a-timeline v-else>
            <a-timeline-item
              v-for="record in detailRecord.approval_records"
              :key="record.id"
              :color="record.action === 'APPROVE' ? 'green' : 'red'"
            >
              <strong>{{ record.approver_name }}</strong>
              <p>{{ record.action === 'APPROVE' ? '审批通过' : '审批驳回' }}</p>
              <small>{{ formatDateTime(record.approved_at) }}</small>
              <p class="timeline-opinion">{{ record.opinion || "未填写审批意见" }}</p>
            </a-timeline-item>
          </a-timeline>
        </div>

        <div class="detail-section">
          <div class="section-head">
            <strong>执行记录</strong>
          </div>
          <a-empty v-if="!detailRecord.execution_record" description="当前尚未执行销毁" />
          <template v-else>
            <a-descriptions :column="1" bordered size="small">
              <a-descriptions-item label="执行人">{{ detailRecord.execution_record.operator_name }}</a-descriptions-item>
              <a-descriptions-item label="执行时间">
                {{ formatDateTime(detailRecord.execution_record.executed_at) }}
              </a-descriptions-item>
              <a-descriptions-item label="执行说明">{{ detailRecord.execution_record.execution_note }}</a-descriptions-item>
              <a-descriptions-item label="销毁前位置">
                {{ detailRecord.execution_record.location_snapshot || "-" }}
              </a-descriptions-item>
            </a-descriptions>
            <div class="attachment-block">
              <strong>执行附件</strong>
              <a-empty
                v-if="!detailRecord.execution_record.attachments.length"
                description="未上传执行附件"
              />
              <a-space v-else direction="vertical">
                <a-button
                  v-for="attachment in detailRecord.execution_record.attachments"
                  :key="attachment.id"
                  type="link"
                  :href="buildDestroyAttachmentUrl(attachment.file_path)"
                  target="_blank"
                >
                  {{ attachment.file_name }}
                </a-button>
              </a-space>
            </div>
          </template>
        </div>
      </template>
    </a-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue"
import { message } from "ant-design-vue"
import { useRoute, useRouter } from "vue-router"

import { fetchArchives, type ArchiveRecord } from "@/api/archives"
import {
  approveDestroyApplication,
  buildDestroyAttachmentUrl,
  createDestroyApplication,
  destroyAttachmentAccept,
  destroyAttachmentMaxSizeMb,
  executeDestroyApplication,
  fetchDestroyApplicationDetail,
  fetchDestroyApplications,
  fetchDestroyApplicationsPage,
  validateDestroyAttachmentFiles,
  type DestroyApplication,
  type DestroyApplicationDetail,
} from "@/api/destruction"
import { useAuthStore } from "@/stores/auth"
import { ARCHIVE_MANAGER_FALLBACK_ROLES, profileHasAnyPermission } from "@/utils/access"
import { getRequestErrorMessage, getRequestErrorStatus } from "@/utils/request"

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const statusLabelMap: Record<string, string> = {
  PENDING_APPROVAL: "待审批",
  APPROVED: "已通过",
  REJECTED: "已驳回",
  EXECUTED: "已执行销毁",
}

const statusColorMap: Record<string, string> = {
  PENDING_APPROVAL: "gold",
  APPROVED: "blue",
  REJECTED: "red",
  EXECUTED: "green",
}

const columns = [
  { title: "档案信息", key: "archive" },
  { title: "申请人", dataIndex: "applicant_name", key: "applicant_name", width: 120 },
  { title: "状态", key: "status", width: 130 },
  { title: "提交时间", key: "submitted_at", width: 180 },
  { title: "操作", key: "actions", width: 220 },
]

const loading = ref(false)
const archiveLoading = ref(false)
const detailLoading = ref(false)
const createSubmitting = ref(false)
const approvalSubmitting = ref(false)
const executeSubmitting = ref(false)
const createModalOpen = ref(false)
const approvalModalOpen = ref(false)
const executeModalOpen = ref(false)
const detailDrawerOpen = ref(false)
const applications = ref<DestroyApplication[]>([])
const applicationPagination = reactive({
  current: 1,
  pageSize: 8,
  total: 0,
})
const archiveCandidates = ref<ArchiveRecord[]>([])
const selectedApplication = ref<DestroyApplication | null>(null)
const detailRecord = ref<DestroyApplicationDetail | null>(null)
const executionFiles = ref<File[]>([])
const executionInputRef = ref<HTMLInputElement | null>(null)

const filters = reactive({
  keyword: "",
  scope: "all" as "mine" | "approval" | "execution" | "all",
  status: undefined as string | undefined,
})

const createForm = reactive({
  archive_id: undefined as number | undefined,
  reason: "",
  basis: "",
})

const approvalForm = reactive({
  action: "APPROVE" as "APPROVE" | "REJECT",
  opinion: "",
})

const executionForm = reactive({
  execution_note: "",
})

const canApprove = computed(() =>
  profileHasAnyPermission(authStore.profile, ["button.destruction.approve"], ["ADMIN"]),
)

const canCreateDestruction = computed(() =>
  profileHasAnyPermission(authStore.profile, ["button.destruction.create"], ARCHIVE_MANAGER_FALLBACK_ROLES),
)

const canExecuteDestruction = computed(() =>
  profileHasAnyPermission(authStore.profile, ["button.destruction.execute"], ARCHIVE_MANAGER_FALLBACK_ROLES),
)

const scopeOptions = computed(() => {
  const options: Array<{ value: "mine" | "approval" | "execution" | "all"; label: string }> = [
    { value: "mine", label: "我发起的" },
  ]
  if (canApprove.value) {
    options.push({ value: "approval", label: "待我审批" })
  }
  if (canExecuteDestruction.value) {
    options.push({ value: "execution", label: "待执行" })
    options.push({ value: "all", label: "全部记录" })
  }
  return options
})

const statusOptions = Object.entries(statusLabelMap).map(([value, label]) => ({ value, label }))

const archiveOptions = computed(() =>
  archiveCandidates.value.map((item) => ({
    value: item.id,
    label: `${item.archive_code} ${item.title}`,
  })),
)

const summaryCards = computed(() => {
  const total = applicationPagination.total
  const pending = applications.value.filter((item) => item.status === "PENDING_APPROVAL").length
  const approved = applications.value.filter((item) => item.status === "APPROVED").length
  const executed = applications.value.filter((item) => item.status === "EXECUTED").length
  return [
    { label: "当前记录", value: total, caption: "当前筛选条件下的销毁申请数量" },
    { label: "待审批", value: pending, caption: "仍需具备销毁审批权限的人员处理的申请数量" },
    { label: "待执行", value: approved, caption: "审批通过但尚未完成销毁执行的数量" },
    { label: "已执行", value: executed, caption: "已经完成销毁留痕并流转结束的数量" },
  ]
})

function formatDateTime(value: string | null) {
  if (!value) {
    return "-"
  }
  return value.replace("T", " ").slice(0, 19)
}

function resetCreateForm() {
  createForm.archive_id = undefined
  createForm.reason = ""
  createForm.basis = ""
}

function resetApprovalForm() {
  approvalForm.action = "APPROVE"
  approvalForm.opinion = ""
}

function resetExecutionForm() {
  executionForm.execution_note = ""
  executionFiles.value = []
  if (executionInputRef.value) {
    executionInputRef.value.value = ""
  }
}

function getDefaultScope() {
  if (canExecuteDestruction.value) {
    return "all" as const
  }
  if (canApprove.value) {
    return "approval" as const
  }
  return "mine" as const
}

function handleReset() {
  filters.keyword = ""
  filters.status = undefined
  filters.scope = getDefaultScope()
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

async function loadApplications() {
  loading.value = true
  try {
    const response = await fetchDestroyApplicationsPage({
      scope: filters.scope,
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
    handleRequestError(error, "加载销毁申请列表失败。")
  } finally {
    loading.value = false
  }
}

async function loadArchiveCandidates() {
  archiveLoading.value = true
  try {
    const response = await fetchArchives({ status: "ON_SHELF" })
    archiveCandidates.value = response.data
  } catch (error) {
    handleRequestError(error, "加载可销毁档案列表失败。")
  } finally {
    archiveLoading.value = false
  }
}

function openCreateModal() {
  if (!canCreateDestruction.value) {
    message.warning("当前账号无权发起销毁申请。")
    return
  }
  resetCreateForm()
  createModalOpen.value = true
  if (!archiveCandidates.value.length) {
    void loadArchiveCandidates()
  }
}

function openApprovalModal(record: DestroyApplication) {
  if (!canApprove.value) {
    message.warning("当前账号无权审批销毁申请。")
    return
  }
  selectedApplication.value = record
  resetApprovalForm()
  approvalModalOpen.value = true
}

function openExecuteModal(record: DestroyApplication) {
  if (!canExecuteDestruction.value) {
    message.warning("当前账号无权执行销毁。")
    return
  }
  selectedApplication.value = record
  resetExecutionForm()
  executeModalOpen.value = true
}

function handleExecutionFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || [])
  const validationMessage = validateDestroyAttachmentFiles(files)
  if (validationMessage) {
    executionFiles.value = []
    input.value = ""
    message.warning(validationMessage)
    return
  }
  executionFiles.value = files
}

async function openDetailDrawer(applicationId: number) {
  detailDrawerOpen.value = true
  detailLoading.value = true
  detailRecord.value = null
  try {
    const response = await fetchDestroyApplicationDetail(applicationId)
    detailRecord.value = response.data
  } catch (error) {
    detailDrawerOpen.value = false
    const status = getRequestErrorStatus(error)
    if (status === 404) {
      message.error("销毁申请不存在或已被删除，请刷新列表后重试。")
      await loadApplications()
      return
    }
    if (status === 403) {
      message.error("当前账号无权查看该销毁申请详情。")
      return
    }
    handleRequestError(error, "加载销毁申请详情失败。")
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

  await openDetailDrawer(applicationId)
  const nextQuery = { ...route.query }
  delete nextQuery.applicationId
  await router.replace({ query: nextQuery })
}

async function handleCreateApplication() {
  if (!canCreateDestruction.value) {
    message.warning("当前账号无权发起销毁申请。")
    return
  }
  if (!createForm.archive_id) {
    message.warning("请选择需要发起销毁的档案。")
    return
  }
  if (!createForm.reason.trim() || !createForm.basis.trim()) {
    message.warning("请完整填写销毁原因和销毁依据。")
    return
  }

  createSubmitting.value = true
  try {
    const response = await createDestroyApplication({
      archive_id: createForm.archive_id,
      reason: createForm.reason.trim(),
      basis: createForm.basis.trim(),
    })
    message.success(response.message)
    createModalOpen.value = false
    resetCreateForm()
    await Promise.all([loadApplications(), loadArchiveCandidates()])
  } catch (error) {
    handleRequestError(error, "创建销毁申请失败。")
  } finally {
    createSubmitting.value = false
  }
}

async function handleSubmitApproval() {
  if (!canApprove.value) {
    message.warning("当前账号无权审批销毁申请。")
    return
  }
  if (!selectedApplication.value) {
    return
  }
  if (approvalForm.action === "REJECT" && !approvalForm.opinion.trim()) {
    message.warning("驳回时必须填写审批意见。")
    return
  }

  approvalSubmitting.value = true
  try {
    const response = await approveDestroyApplication(selectedApplication.value.id, {
      action: approvalForm.action,
      opinion: approvalForm.opinion.trim() || undefined,
    })
    message.success(response.message)
    approvalModalOpen.value = false
    resetApprovalForm()
    await loadApplications()
    if (detailDrawerOpen.value) {
      await openDetailDrawer(response.data.id)
    }
  } catch (error) {
    const status = getRequestErrorStatus(error)
    if (status === 404) {
      message.error("销毁申请不存在或状态已变化，请刷新列表后重试。")
      approvalModalOpen.value = false
      resetApprovalForm()
      selectedApplication.value = null
      await loadApplications()
      return
    }
    if (status === 403) {
      message.error("当前账号无权审批该销毁申请。")
      approvalModalOpen.value = false
      resetApprovalForm()
      selectedApplication.value = null
      await loadApplications()
      return
    }
    handleRequestError(error, "处理销毁审批失败。")
  } finally {
    approvalSubmitting.value = false
  }
}

async function handleSubmitExecution() {
  if (!canExecuteDestruction.value) {
    message.warning("当前账号无权执行销毁。")
    return
  }
  if (!selectedApplication.value) {
    return
  }
  if (!executionForm.execution_note.trim()) {
    message.warning("请填写销毁执行说明。")
    return
  }
  const validationMessage = validateDestroyAttachmentFiles(executionFiles.value)
  if (validationMessage) {
    message.warning(validationMessage)
    return
  }

  executeSubmitting.value = true
  try {
    const response = await executeDestroyApplication(selectedApplication.value.id, {
      execution_note: executionForm.execution_note.trim(),
      attachment_files: executionFiles.value,
    })
    message.success(response.message)
    executeModalOpen.value = false
    resetExecutionForm()
    await Promise.all([loadApplications(), loadArchiveCandidates()])
    if (detailDrawerOpen.value) {
      await openDetailDrawer(response.data.id)
    }
  } catch (error) {
    const status = getRequestErrorStatus(error)
    if (status === 404) {
      message.error("销毁申请不存在或状态已变化，请刷新列表后重试。")
      executeModalOpen.value = false
      resetExecutionForm()
      selectedApplication.value = null
      await loadApplications()
      return
    }
    if (status === 403) {
      message.error("当前账号无权执行该销毁申请。")
      executeModalOpen.value = false
      resetExecutionForm()
      selectedApplication.value = null
      await loadApplications()
      return
    }
    handleRequestError(error, "执行销毁失败。")
  } finally {
    executeSubmitting.value = false
  }
}

function handleRequestError(error: unknown, fallbackMessage: string) {
  message.error(getRequestErrorMessage(error, fallbackMessage))
}

onMounted(() => {
  filters.scope = getDefaultScope()
  void loadApplications()
})

watch(
  () => route.query.applicationId,
  () => {
    void consumeRouteApplicationId()
  },
  { immediate: true },
)

watch(
  () => [canApprove.value, canExecuteDestruction.value],
  () => {
    if (!scopeOptions.value.some((item) => item.value === filters.scope)) {
      filters.scope = getDefaultScope()
    }
  },
)
</script>

<style scoped>
.destruction-page {
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
  grid-template-columns: minmax(0, 1.5fr) 180px 180px;
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

.archive-cell {
  display: grid;
  gap: 4px;
}

.archive-cell span {
  color: #667085;
  font-size: 12px;
}

.modal-alert,
.modal-form {
  margin-top: 16px;
}

.detail-section {
  display: grid;
  gap: 16px;
  margin-bottom: 24px;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.timeline-opinion {
  margin: 6px 0 0;
  color: #475467;
}

.attachment-block {
  display: grid;
  gap: 12px;
}

.upload-input {
  display: none;
}

.upload-button {
  width: fit-content;
}

.file-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 10px;
}

.file-list span {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(10, 113, 82, 0.08);
  color: #0a7152;
}

@media (max-width: 960px) {
  .toolbar-grid {
    grid-template-columns: 1fr;
  }

  .toolbar-actions {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
