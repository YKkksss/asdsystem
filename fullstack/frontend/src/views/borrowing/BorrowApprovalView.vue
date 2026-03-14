<template>
  <section class="approval-page">
    <div class="summary-grid">
      <a-card v-for="item in summaryCards" :key="item.label" :bordered="false" class="summary-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.caption }}</small>
      </a-card>
    </div>

    <a-card :bordered="false" class="panel-card">
      <div class="toolbar">
        <a-input-search
          v-model:value="keyword"
          allow-clear
          placeholder="按申请编号、档号、题名或申请人搜索"
          @search="loadApplications"
        />
        <a-button type="primary" @click="loadApplications">刷新审批列表</a-button>
      </div>

      <a-table
        :columns="columns"
        :data-source="applications"
        :loading="loading"
        row-key="id"
        :pagination="{ pageSize: 8, showSizeChanger: false }"
      >
        <template #emptyText>
          <a-empty description="当前没有待审批借阅申请" />
        </template>

        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'archive'">
            <div class="archive-cell">
              <strong>{{ record.archive_title }}</strong>
              <span>{{ record.archive_code }}</span>
            </div>
          </template>

          <template v-else-if="column.key === 'status'">
            <a-tag color="processing">{{ statusLabelMap[record.status] || record.status }}</a-tag>
          </template>

          <template v-else-if="column.key === 'expected_return_at'">
            {{ formatDateTime(record.expected_return_at) }}
          </template>

          <template v-else-if="column.key === 'actions'">
            <a-space wrap>
              <a-button type="link" @click="openActionModal(record, 'APPROVE')">审批通过</a-button>
              <a-button danger type="link" @click="openActionModal(record, 'REJECT')">驳回申请</a-button>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <a-modal
      v-model:open="modalOpen"
      :confirm-loading="submitting"
      :ok-text="pendingAction === 'APPROVE' ? '确认通过' : '确认驳回'"
      :title="pendingAction === 'APPROVE' ? '审批通过借阅申请' : '驳回借阅申请'"
      @ok="handleSubmitAction"
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
          <a-descriptions-item label="用途">{{ selectedApplication.purpose }}</a-descriptions-item>
          <a-descriptions-item label="预计归还时间">
            {{ formatDateTime(selectedApplication.expected_return_at) }}
          </a-descriptions-item>
        </a-descriptions>

        <a-form layout="vertical" class="modal-form">
          <a-form-item :label="pendingAction === 'APPROVE' ? '审批意见' : '驳回原因'">
            <a-textarea
              v-model:value="actionForm.opinion"
              :rows="4"
              :placeholder="pendingAction === 'APPROVE' ? '可补充审批说明' : '驳回时必须填写原因'"
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

import {
  approveBorrowApplication,
  fetchBorrowApplications,
  type BorrowApplication,
} from "@/api/borrowing"
import { getRequestErrorMessage, getRequestErrorStatus } from "@/utils/request"

const statusLabelMap: Record<string, string> = {
  PENDING_APPROVAL: "待审批",
}

const columns = [
  { title: "档案信息", key: "archive" },
  { title: "申请人", dataIndex: "applicant_name", key: "applicant_name", width: 120 },
  { title: "预计归还", key: "expected_return_at", width: 180 },
  { title: "状态", key: "status", width: 110 },
  { title: "操作", key: "actions", width: 180 },
]

const loading = ref(false)
const submitting = ref(false)
const modalOpen = ref(false)
const keyword = ref("")
const applications = ref<BorrowApplication[]>([])
const selectedApplication = ref<BorrowApplication | null>(null)
const pendingAction = ref<"APPROVE" | "REJECT">("APPROVE")
const actionForm = reactive({
  opinion: "",
})

const summaryCards = computed(() => {
  const total = applications.value.length
  const urgent = applications.value.filter((item) => item.is_overdue).length
  return [
    { label: "待审批数量", value: total, caption: "当前由我处理的借阅审批单数" },
    { label: "涉及超期", value: urgent, caption: "申请人已有超期标记的单据数量" },
  ]
})

function formatDateTime(value: string | null) {
  if (!value) {
    return "-"
  }
  return value.replace("T", " ").slice(0, 19)
}

function resetModal() {
  actionForm.opinion = ""
}

function openActionModal(application: BorrowApplication, action: "APPROVE" | "REJECT") {
  selectedApplication.value = application
  pendingAction.value = action
  resetModal()
  modalOpen.value = true
}

async function loadApplications() {
  loading.value = true
  try {
    const response = await fetchBorrowApplications({
      scope: "approval",
      keyword: keyword.value.trim() || undefined,
    })
    applications.value = response.data
  } catch (error) {
    handleRequestError(error, "加载待审批借阅申请失败。")
  } finally {
    loading.value = false
  }
}

async function handleSubmitAction() {
  if (!selectedApplication.value) {
    return
  }
  if (pendingAction.value === "REJECT" && !actionForm.opinion.trim()) {
    message.warning("驳回时必须填写审批意见。")
    return
  }

  submitting.value = true
  try {
    const response = await approveBorrowApplication(selectedApplication.value.id, {
      action: pendingAction.value,
      opinion: actionForm.opinion.trim() || undefined,
    })
    message.success(response.message)
    modalOpen.value = false
    resetModal()
    await loadApplications()
  } catch (error) {
    const status = getRequestErrorStatus(error)
    if (status === 404) {
      message.error("借阅申请不存在或状态已变化，请刷新列表后重试。")
      modalOpen.value = false
      selectedApplication.value = null
      resetModal()
      await loadApplications()
      return
    }
    if (status === 403) {
      message.error("当前账号无权审批该借阅申请。")
      modalOpen.value = false
      selectedApplication.value = null
      resetModal()
      await loadApplications()
      return
    }
    handleRequestError(error, "处理借阅审批失败。")
  } finally {
    submitting.value = false
  }
}

function handleRequestError(error: unknown, fallbackMessage: string) {
  const status = getRequestErrorStatus(error)
  if (status === 403) {
    message.error("当前账号无权查看待审批借阅申请。")
    return
  }
  message.error(getRequestErrorMessage(error, fallbackMessage))
}

onMounted(() => {
  void loadApplications()
})
</script>

<style scoped>
.approval-page {
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

.toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  margin-bottom: 16px;
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

@media (max-width: 720px) {
  .toolbar {
    grid-template-columns: 1fr;
  }
}
</style>
