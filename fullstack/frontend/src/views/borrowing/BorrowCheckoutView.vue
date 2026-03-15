<template>
  <section class="checkout-page">
    <a-alert
      v-if="!canManageArchives"
      show-icon
      type="warning"
      message="当前账号不是管理员或档案员，不能办理出库登记。"
    />

    <template v-else>
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
            @search="handleApplyFilters"
          />
          <a-button type="primary" @click="handleApplyFilters">刷新待出库列表</a-button>
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
            <a-empty description="暂无待出库借阅申请" />
          </template>

          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'archive'">
              <div class="archive-cell">
                <strong>{{ record.archive_title }}</strong>
                <span>{{ record.archive_code }}</span>
              </div>
            </template>

            <template v-else-if="column.key === 'expected_return_at'">
              {{ formatDateTime(record.expected_return_at) }}
            </template>

            <template v-else-if="column.key === 'actions'">
              <a-button type="link" @click="openCheckoutModal(record)">办理出库</a-button>
            </template>
          </template>
        </a-table>
      </a-card>
    </template>

    <a-modal
      v-model:open="modalOpen"
      title="办理借阅出库"
      ok-text="确认出库"
      :confirm-loading="submitting"
      @ok="handleSubmitCheckout"
    >
      <template v-if="selectedApplication">
        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="申请编号">{{ selectedApplication.application_no }}</a-descriptions-item>
          <a-descriptions-item label="档案">{{ selectedApplication.archive_title }}</a-descriptions-item>
          <a-descriptions-item label="申请人">{{ selectedApplication.applicant_name }}</a-descriptions-item>
          <a-descriptions-item label="预计归还">
            {{ formatDateTime(selectedApplication.expected_return_at) }}
          </a-descriptions-item>
          <a-descriptions-item label="借阅用途">{{ selectedApplication.purpose }}</a-descriptions-item>
        </a-descriptions>

        <a-form layout="vertical" class="modal-form">
          <a-form-item label="出库备注">
            <a-textarea
              v-model:value="checkoutNote"
              :rows="4"
              placeholder="可填写线下签收情况、交接说明或其他备注"
            />
          </a-form-item>
        </a-form>
      </template>
    </a-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { message } from "ant-design-vue"

import {
  checkoutBorrowApplication,
  fetchBorrowApplicationsPage,
  type BorrowApplication,
} from "@/api/borrowing"
import { useAuthStore } from "@/stores/auth"
import { getRequestErrorMessage, getRequestErrorStatus } from "@/utils/request"

const authStore = useAuthStore()

const canManageArchives = computed(() =>
  Boolean(authStore.profile?.roles.some((role) => ["ADMIN", "ARCHIVIST"].includes(role.role_code))),
)

const columns = [
  { title: "档案信息", key: "archive" },
  { title: "申请人", dataIndex: "applicant_name", key: "applicant_name", width: 120 },
  { title: "预计归还", key: "expected_return_at", width: 180 },
  { title: "借阅用途", dataIndex: "purpose", key: "purpose" },
  { title: "操作", key: "actions", width: 120 },
]

const loading = ref(false)
const submitting = ref(false)
const modalOpen = ref(false)
const keyword = ref("")
const checkoutNote = ref("")
const applications = ref<BorrowApplication[]>([])
const applicationPagination = ref({
  current: 1,
  pageSize: 8,
  total: 0,
})
const selectedApplication = ref<BorrowApplication | null>(null)

const summaryCards = computed(() => [
  {
    label: "待出库数量",
    value: applicationPagination.value.total,
    caption: "当前筛选条件下审批通过后待档案员处理的申请单数",
  },
  {
    label: "今日待办",
    value: applications.value.filter((item) => item.created_at.slice(0, 10) === new Date().toISOString().slice(0, 10)).length,
    caption: "当前页中今日新进入出库环节的申请数量",
  },
])

function formatDateTime(value: string | null) {
  if (!value) {
    return "-"
  }
  return value.replace("T", " ").slice(0, 19)
}

function openCheckoutModal(application: BorrowApplication) {
  selectedApplication.value = application
  checkoutNote.value = ""
  modalOpen.value = true
}

function handleApplyFilters() {
  applicationPagination.value.current = 1
  void loadApplications()
}

function handleApplicationTableChange(page: number, pageSize: number) {
  applicationPagination.value.current = page
  applicationPagination.value.pageSize = pageSize
  void loadApplications()
}

async function loadApplications() {
  if (!canManageArchives.value) {
    applications.value = []
    applicationPagination.value.total = 0
    return
  }

  loading.value = true
  try {
    const response = await fetchBorrowApplicationsPage({
      scope: "checkout",
      keyword: keyword.value.trim() || undefined,
      page: applicationPagination.value.current,
      page_size: applicationPagination.value.pageSize,
    })
    applications.value = response.data.items
    applicationPagination.value.total = response.data.pagination.total
    applicationPagination.value.current = response.data.pagination.page
    applicationPagination.value.pageSize = response.data.pagination.page_size
  } catch (error) {
    handleRequestError(error, "加载待出库借阅申请失败。")
  } finally {
    loading.value = false
  }
}

async function handleSubmitCheckout() {
  if (!selectedApplication.value) {
    return
  }

  submitting.value = true
  try {
    const response = await checkoutBorrowApplication(selectedApplication.value.id, {
      checkout_note: checkoutNote.value.trim() || undefined,
    })
    message.success(response.message)
    modalOpen.value = false
    await loadApplications()
  } catch (error) {
    const status = getRequestErrorStatus(error)
    if (status === 404) {
      message.error("借阅申请不存在或状态已变化，请刷新列表后重试。")
      modalOpen.value = false
      selectedApplication.value = null
      checkoutNote.value = ""
      await loadApplications()
      return
    }
    if (status === 403) {
      message.error("当前账号无权办理该借阅出库。")
      modalOpen.value = false
      selectedApplication.value = null
      checkoutNote.value = ""
      await loadApplications()
      return
    }
    handleRequestError(error, "办理借阅出库失败。")
  } finally {
    submitting.value = false
  }
}

function handleRequestError(error: unknown, fallbackMessage: string) {
  const status = getRequestErrorStatus(error)
  if (status === 403) {
    message.error("当前账号无权查看待出库借阅申请。")
    return
  }
  message.error(getRequestErrorMessage(error, fallbackMessage))
}

onMounted(() => {
  void loadApplications()
})
</script>

<style scoped>
.checkout-page {
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

.modal-form {
  margin-top: 16px;
}

@media (max-width: 720px) {
  .toolbar {
    grid-template-columns: 1fr;
  }
}
</style>
