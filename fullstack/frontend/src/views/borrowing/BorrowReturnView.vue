<template>
  <section class="return-page">
    <div class="summary-grid">
      <a-card v-for="item in summaryCards" :key="item.label" :bordered="false" class="summary-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.caption }}</small>
      </a-card>
    </div>

    <a-row :gutter="[20, 20]">
      <a-col :xs="24" :xl="canManageArchives ? 12 : 24">
        <a-card :bordered="false" class="panel-card">
          <template #title>我的归还任务</template>

          <a-table
            :columns="myColumns"
            :data-source="activeBorrowedApplications"
            :loading="myLoading"
            row-key="id"
            :pagination="{ pageSize: 6, showSizeChanger: false }"
          >
            <template #emptyText>
              <a-empty description="当前没有待归还借阅档案" />
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
                {{ formatDateTime(record.expected_return_at) }}
              </template>

              <template v-else-if="column.key === 'actions'">
                <a-button type="link" @click="openReturnModal(record)">提交归还</a-button>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>

      <a-col v-if="canManageArchives" :xs="24" :xl="12">
        <a-card :bordered="false" class="panel-card">
          <template #title>归还确认待办</template>

          <a-table
            :columns="confirmColumns"
            :data-source="pendingConfirmApplications"
            :loading="confirmLoading"
            row-key="id"
            :pagination="{ pageSize: 6, showSizeChanger: false }"
          >
            <template #emptyText>
              <a-empty description="当前没有待确认归还记录" />
            </template>

            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'archive'">
                <div class="archive-cell">
                  <strong>{{ record.archive_title }}</strong>
                  <span>{{ record.archive_code }}</span>
                </div>
              </template>

              <template v-else-if="column.key === 'return_status'">
                <a-tag color="gold">{{ returnStatusLabelMap[record.return_status || "SUBMITTED"] }}</a-tag>
              </template>

              <template v-else-if="column.key === 'actions'">
                <a-button type="link" @click="openConfirmModal(record)">处理确认</a-button>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>
    </a-row>

    <a-modal
      v-model:open="returnModalOpen"
      title="提交归还"
      ok-text="确认提交"
      :confirm-loading="returnSubmitting"
      @ok="handleSubmitReturn"
    >
      <template v-if="selectedReturnApplication">
        <a-alert
          show-icon
          type="info"
          class="modal-alert"
          :message="`归还单号：${selectedReturnApplication.application_no}`"
        />

        <a-descriptions :column="1" bordered size="small">
          <a-descriptions-item label="档案">{{ selectedReturnApplication.archive_title }}</a-descriptions-item>
          <a-descriptions-item label="预计归还时间">
            {{ formatDateTime(selectedReturnApplication.expected_return_at) }}
          </a-descriptions-item>
          <a-descriptions-item label="借阅用途">{{ selectedReturnApplication.purpose }}</a-descriptions-item>
        </a-descriptions>

        <a-alert
          class="upload-guide"
          show-icon
          type="info"
          :message="`归还附件支持 PDF、JPG、JPEG、PNG，单个文件不超过 ${borrowReturnAttachmentMaxSizeMb} MB。`"
        />

        <a-form layout="vertical" class="modal-form">
          <a-form-item label="交接说明">
            <a-textarea
              v-model:value="returnForm.handover_note"
              :rows="3"
              placeholder="补充说明交接情况、附件内容或异常说明"
            />
          </a-form-item>

          <a-form-item label="归还照片">
            <input
              ref="photoInputRef"
              class="upload-input"
              multiple
              type="file"
              :accept="borrowReturnAttachmentAccept"
              @change="handlePhotoFileChange"
            />
            <a-button class="upload-button" @click="photoInputRef?.click()">选择照片</a-button>
            <div v-if="returnForm.photo_files.length" class="file-list">
              <span v-for="file in returnForm.photo_files" :key="file.name">{{ file.name }}</span>
            </div>
          </a-form-item>

          <a-form-item label="交接单">
            <input
              ref="handoverInputRef"
              class="upload-input"
              multiple
              type="file"
              :accept="borrowReturnAttachmentAccept"
              @change="handleHandoverFileChange"
            />
            <a-button class="upload-button" @click="handoverInputRef?.click()">选择交接单</a-button>
            <div v-if="returnForm.handover_files.length" class="file-list">
              <span v-for="file in returnForm.handover_files" :key="file.name">{{ file.name }}</span>
            </div>
          </a-form-item>
        </a-form>
      </template>
    </a-modal>

    <a-modal
      v-model:open="confirmModalOpen"
      title="归还确认"
      ok-text="提交确认"
      :confirm-loading="confirmSubmitting"
      @ok="handleSubmitConfirm"
    >
      <a-spin :spinning="confirmDetailLoading">
        <template v-if="selectedConfirmApplication">
          <a-radio-group v-model:value="confirmForm.approved" class="confirm-choice">
            <a-radio :value="true">验收通过并重新入库</a-radio>
            <a-radio :value="false">验收不通过</a-radio>
          </a-radio-group>

          <a-descriptions :column="1" bordered size="small">
            <a-descriptions-item label="申请编号">{{ selectedConfirmApplication.application_no }}</a-descriptions-item>
            <a-descriptions-item label="档案">{{ selectedConfirmApplication.archive_title }}</a-descriptions-item>
            <a-descriptions-item label="申请人">{{ selectedConfirmApplication.applicant_name }}</a-descriptions-item>
            <a-descriptions-item label="交接说明">
              {{ selectedConfirmApplication.return_record?.handover_note || "未填写" }}
            </a-descriptions-item>
          </a-descriptions>

          <div class="attachment-panel">
            <a
              v-for="item in selectedConfirmApplication.return_record?.attachments || []"
              :key="item.id"
              :href="buildBorrowAttachmentUrl(item.file_path)"
              class="attachment-link"
              target="_blank"
              rel="noreferrer"
            >
              {{ item.file_name }}
            </a>
          </div>

          <a-form layout="vertical" class="modal-form">
            <a-form-item v-if="confirmForm.approved" label="归还后位置">
              <a-select
                v-model:value="confirmForm.location_after_return_id"
                allow-clear
                :loading="locationLoading"
                :options="locationOptions"
                placeholder="如需调整位置，可重新选择"
                show-search
                :filter-option="filterOption"
              />
            </a-form-item>

            <a-form-item label="验收备注">
              <a-textarea
                v-model:value="confirmForm.confirm_note"
                :rows="3"
                :placeholder="confirmForm.approved ? '可填写重新入库说明' : '请填写验收不通过原因'"
              />
            </a-form-item>
          </a-form>
        </template>
      </a-spin>
    </a-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue"
import { message } from "ant-design-vue"
import type { SelectProps } from "ant-design-vue"

import { fetchArchiveLocations } from "@/api/archives"
import {
  buildBorrowAttachmentUrl,
  borrowReturnAttachmentAccept,
  borrowReturnAttachmentMaxSizeMb,
  confirmBorrowReturn,
  fetchBorrowApplicationDetail,
  fetchBorrowApplications,
  submitBorrowReturn,
  validateBorrowReturnAttachmentFiles,
  type BorrowApplication,
  type BorrowApplicationDetail,
} from "@/api/borrowing"
import { useAuthStore } from "@/stores/auth"
import { getRequestErrorMessage, getRequestErrorStatus } from "@/utils/request"

const authStore = useAuthStore()

const statusLabelMap: Record<string, string> = {
  CHECKED_OUT: "借出中",
  OVERDUE: "已超期",
  RETURNED: "已归还",
}

const statusColorMap: Record<string, string> = {
  CHECKED_OUT: "gold",
  OVERDUE: "volcano",
  RETURNED: "green",
}

const returnStatusLabelMap: Record<string, string> = {
  SUBMITTED: "已提交归还",
  CONFIRMED: "已确认入库",
  REJECTED: "归还验收不通过",
}

const canManageArchives = computed(() =>
  Boolean(authStore.profile?.roles.some((role) => ["ADMIN", "ARCHIVIST"].includes(role.role_code))),
)

const myColumns = [
  { title: "档案信息", key: "archive" },
  { title: "状态", key: "status", width: 120 },
  { title: "预计归还", key: "expected_return_at", width: 180 },
  { title: "操作", key: "actions", width: 120 },
]

const confirmColumns = [
  { title: "档案信息", key: "archive" },
  { title: "申请人", dataIndex: "applicant_name", key: "applicant_name", width: 120 },
  { title: "归还状态", key: "return_status", width: 130 },
  { title: "操作", key: "actions", width: 120 },
]

const myLoading = ref(false)
const confirmLoading = ref(false)
const locationLoading = ref(false)
const returnSubmitting = ref(false)
const confirmSubmitting = ref(false)
const confirmDetailLoading = ref(false)

const myApplications = ref<BorrowApplication[]>([])
const pendingConfirmApplications = ref<BorrowApplication[]>([])
const locationOptions = ref<SelectProps["options"]>([])

const returnModalOpen = ref(false)
const confirmModalOpen = ref(false)
const selectedReturnApplication = ref<BorrowApplication | null>(null)
const selectedConfirmApplication = ref<BorrowApplicationDetail | null>(null)
const photoInputRef = ref<HTMLInputElement | null>(null)
const handoverInputRef = ref<HTMLInputElement | null>(null)

const returnForm = reactive({
  handover_note: "",
  photo_files: [] as File[],
  handover_files: [] as File[],
})

const confirmForm = reactive({
  approved: true,
  location_after_return_id: undefined as number | undefined,
  confirm_note: "",
})

const activeBorrowedApplications = computed(() =>
  myApplications.value.filter((item) => ["CHECKED_OUT", "OVERDUE"].includes(item.status)),
)

const summaryCards = computed(() => [
  {
    label: "待归还",
    value: activeBorrowedApplications.value.length,
    caption: "当前账号仍需提交归还的借阅申请数量",
  },
  {
    label: "超期中",
    value: activeBorrowedApplications.value.filter((item) => item.status === "OVERDUE").length,
    caption: "已经超过预计归还时间的申请数量",
  },
  {
    label: "待确认",
    value: pendingConfirmApplications.value.length,
    caption: "等待档案员验收确认的归还记录数量",
  },
])

function filterOption(input: string, option?: { label?: unknown }) {
  return String(option?.label || "").toLowerCase().includes(input.toLowerCase())
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "-"
  }
  return value.replace("T", " ").slice(0, 19)
}

function resetReturnForm() {
  returnForm.handover_note = ""
  returnForm.photo_files = []
  returnForm.handover_files = []
  if (photoInputRef.value) {
    photoInputRef.value.value = ""
  }
  if (handoverInputRef.value) {
    handoverInputRef.value.value = ""
  }
}

function resetConfirmForm() {
  confirmForm.approved = true
  confirmForm.location_after_return_id = undefined
  confirmForm.confirm_note = ""
}

function applyValidatedReturnFiles(files: File[], targetField: "photo_files" | "handover_files", input: HTMLInputElement) {
  const validationMessage = validateBorrowReturnAttachmentFiles(files)
  if (validationMessage) {
    returnForm[targetField] = []
    input.value = ""
    message.warning(validationMessage)
    return
  }
  returnForm[targetField] = files
}

function handlePhotoFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  applyValidatedReturnFiles(Array.from(input.files || []), "photo_files", input)
}

function handleHandoverFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  applyValidatedReturnFiles(Array.from(input.files || []), "handover_files", input)
}

function openReturnModal(application: BorrowApplication) {
  selectedReturnApplication.value = application
  resetReturnForm()
  returnModalOpen.value = true
}

async function openConfirmModal(application: BorrowApplication) {
  confirmModalOpen.value = true
  confirmDetailLoading.value = true
  resetConfirmForm()
  selectedConfirmApplication.value = null
  try {
    const response = await fetchBorrowApplicationDetail(application.id)
    selectedConfirmApplication.value = response.data
  } catch (error) {
    confirmModalOpen.value = false
    const status = getRequestErrorStatus(error)
    if (status === 404) {
      message.error("归还确认记录不存在或状态已变化，请刷新列表后重试。")
      await Promise.all([loadMyApplications(), loadPendingConfirmApplications()])
      return
    }
    if (status === 403) {
      message.error("当前账号无权处理该归还记录。")
      await loadPendingConfirmApplications()
      return
    }
    handleRequestError(error, "加载归还详情失败。")
  } finally {
    confirmDetailLoading.value = false
  }
}

async function loadMyApplications() {
  myLoading.value = true
  try {
    const response = await fetchBorrowApplications({ scope: "mine" })
    myApplications.value = response.data
  } catch (error) {
    handleRequestError(error, "加载我的借阅申请失败。")
  } finally {
    myLoading.value = false
  }
}

async function loadPendingConfirmApplications() {
  if (!canManageArchives.value) {
    pendingConfirmApplications.value = []
    return
  }

  confirmLoading.value = true
  try {
    const response = await fetchBorrowApplications({ scope: "return" })
    pendingConfirmApplications.value = response.data
  } catch (error) {
    handleRequestError(error, "加载待确认归还记录失败。")
  } finally {
    confirmLoading.value = false
  }
}

async function loadLocationOptions() {
  if (!canManageArchives.value) {
    return
  }

  locationLoading.value = true
  try {
    const response = await fetchArchiveLocations()
    locationOptions.value = response.data.map((item) => ({
      value: item.id,
      label: item.full_location_code,
    }))
  } catch (error) {
    handleRequestError(error, "加载实体位置失败。")
  } finally {
    locationLoading.value = false
  }
}

async function handleSubmitReturn() {
  if (!selectedReturnApplication.value) {
    return
  }
  if (!returnForm.photo_files.length && !returnForm.handover_files.length) {
    message.warning("归还时至少需要上传照片或交接单中的一种。")
    return
  }
  const photoValidationMessage = validateBorrowReturnAttachmentFiles(returnForm.photo_files)
  if (photoValidationMessage) {
    message.warning(photoValidationMessage)
    return
  }
  const handoverValidationMessage = validateBorrowReturnAttachmentFiles(returnForm.handover_files)
  if (handoverValidationMessage) {
    message.warning(handoverValidationMessage)
    return
  }

  returnSubmitting.value = true
  try {
    const response = await submitBorrowReturn(selectedReturnApplication.value.id, {
      handover_note: returnForm.handover_note.trim() || undefined,
      photo_files: returnForm.photo_files,
      handover_files: returnForm.handover_files,
    })
    message.success(response.message)
    returnModalOpen.value = false
    resetReturnForm()
    await loadMyApplications()
    await loadPendingConfirmApplications()
  } catch (error) {
    const status = getRequestErrorStatus(error)
    if (status === 404) {
      message.error("借阅申请不存在或状态已变化，请刷新列表后重试。")
      returnModalOpen.value = false
      selectedReturnApplication.value = null
      resetReturnForm()
      await Promise.all([loadMyApplications(), loadPendingConfirmApplications()])
      return
    }
    if (status === 403) {
      message.error("当前账号无权提交该归还记录。")
      returnModalOpen.value = false
      selectedReturnApplication.value = null
      resetReturnForm()
      await loadMyApplications()
      return
    }
    handleRequestError(error, "提交归还失败。")
  } finally {
    returnSubmitting.value = false
  }
}

async function handleSubmitConfirm() {
  if (!selectedConfirmApplication.value) {
    return
  }
  if (!confirmForm.approved && !confirmForm.confirm_note.trim()) {
    message.warning("归还验收不通过时必须填写备注。")
    return
  }

  confirmSubmitting.value = true
  try {
    const response = await confirmBorrowReturn(selectedConfirmApplication.value.id, {
      approved: confirmForm.approved,
      location_after_return_id: confirmForm.approved ? confirmForm.location_after_return_id : undefined,
      confirm_note: confirmForm.confirm_note.trim() || undefined,
    })
    message.success(response.message)
    confirmModalOpen.value = false
    resetConfirmForm()
    await loadMyApplications()
    await loadPendingConfirmApplications()
  } catch (error) {
    const status = getRequestErrorStatus(error)
    if (status === 404) {
      message.error("归还记录不存在或状态已变化，请刷新列表后重试。")
      confirmModalOpen.value = false
      selectedConfirmApplication.value = null
      resetConfirmForm()
      await Promise.all([loadMyApplications(), loadPendingConfirmApplications()])
      return
    }
    if (status === 403) {
      message.error("当前账号无权处理归还确认。")
      confirmModalOpen.value = false
      selectedConfirmApplication.value = null
      resetConfirmForm()
      await loadPendingConfirmApplications()
      return
    }
    handleRequestError(error, "处理归还确认失败。")
  } finally {
    confirmSubmitting.value = false
  }
}

function handleRequestError(error: unknown, fallbackMessage: string) {
  message.error(getRequestErrorMessage(error, fallbackMessage))
}

onMounted(() => {
  void loadMyApplications()
  void loadPendingConfirmApplications()
  void loadLocationOptions()
})
</script>

<style scoped>
.return-page {
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

.archive-cell {
  display: grid;
  gap: 4px;
}

.archive-cell span {
  color: #667085;
  font-size: 12px;
}

.modal-alert,
.modal-form,
.attachment-panel {
  margin-top: 16px;
}

.upload-guide {
  margin-top: 16px;
}

.upload-input {
  display: none;
}

.upload-button {
  width: fit-content;
}

.file-list,
.attachment-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.file-list span,
.attachment-link {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(10, 113, 82, 0.08);
  color: #0a7152;
}

.confirm-choice {
  margin-bottom: 16px;
}
</style>
