<template>
  <section class="create-page">
    <template v-if="canManageArchives">
      <a-row :gutter="[20, 20]">
        <a-col :xs="24" :xl="16">
          <a-card :bordered="false" class="create-card">
            <template #title>{{ formTitle }}</template>

            <a-spin :spinning="pageLoading">
              <a-alert
                v-if="isEditMode"
                class="form-alert"
                type="info"
                show-icon
                message="当前为档案编辑模式，保存后将自动生成新的修订记录并保留修改留痕。"
              />

              <a-form
                :model="formState"
                layout="vertical"
                @finish="handleSubmit"
              >
                <a-row :gutter="[16, 0]">
                  <a-col :xs="24" :md="12">
                    <a-form-item label="档号" name="archive_code" :rules="requiredRules">
                      <a-input v-model:value="formState.archive_code" placeholder="例如：A2026-0001" />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24" :md="12">
                    <a-form-item label="题名" name="title" :rules="requiredRules">
                      <a-input v-model:value="formState.title" placeholder="请输入档案题名" />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24" :md="8">
                    <a-form-item label="年度" name="year" :rules="yearRules">
                      <a-input-number v-model:value="formState.year" :min="1000" :max="9999" class="full-width" />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24" :md="8">
                    <a-form-item label="保管期限" name="retention_period" :rules="requiredRules">
                      <a-select
                        v-model:value="formState.retention_period"
                        placeholder="请选择保管期限"
                        :options="retentionOptions"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24" :md="8">
                    <a-form-item label="密级" name="security_level" :rules="requiredRules">
                      <a-select
                        v-model:value="formState.security_level"
                        placeholder="请选择密级"
                        :options="securityOptions"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24" :md="12">
                    <a-form-item label="责任部门">
                      <a-select
                        v-model:value="formState.responsible_dept_id"
                        allow-clear
                        placeholder="默认使用当前登录部门"
                        :options="departmentOptions"
                        :loading="optionsLoading"
                        show-search
                        option-filter-prop="label"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24" :md="12">
                    <a-form-item label="责任人">
                      <a-input v-model:value="formState.responsible_person" placeholder="请输入责任人姓名" />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24" :md="12">
                    <a-form-item label="形成日期">
                      <a-input v-model:value="formState.formed_at" placeholder="格式：YYYY-MM-DD" />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24" :md="12">
                    <a-form-item label="实体位置">
                      <a-select
                        v-model:value="formState.location_id"
                        allow-clear
                        placeholder="请选择实体位置"
                        :options="locationOptions"
                        :loading="optionsLoading"
                        show-search
                        :filter-option="filterOption"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24" :md="12">
                    <a-form-item label="载体类型">
                      <a-input v-model:value="formState.carrier_type" placeholder="例如：纸质、照片、图纸" />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24" :md="12">
                    <a-form-item label="页数">
                      <a-input-number v-model:value="formState.page_count" :min="1" class="full-width" />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24">
                    <a-form-item label="关键词">
                      <a-input v-model:value="formState.keywords" placeholder="多个关键词可用逗号分隔" />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24">
                    <a-form-item label="摘要">
                      <a-textarea
                        v-model:value="formState.summary"
                        :rows="4"
                        placeholder="请输入档案摘要或背景说明"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24">
                    <a-form-item :label="isEditMode ? '修订说明' : '首次修订说明'">
                      <a-input
                        v-model:value="formState.revision_remark"
                        :placeholder="isEditMode ? '例如：补充摘要、修正责任部门' : '例如：首次入库、补录历史档案'"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>

                <div class="form-actions">
                  <a-button @click="handleReset">重置</a-button>
                  <RouterLink to="/archives/records">
                    <a-button>返回列表</a-button>
                  </RouterLink>
                  <a-button html-type="submit" type="primary" :loading="submitting">
                    {{ submitButtonText }}
                  </a-button>
                </div>
              </a-form>
            </a-spin>
          </a-card>
        </a-col>

        <a-col :xs="24" :xl="8">
          <a-card :bordered="false" class="guide-card">
            <template #title>{{ guideTitle }}</template>
            <ul class="guide-list">
              <li v-for="item in guideItems" :key="item">{{ item }}</li>
            </ul>
          </a-card>
        </a-col>
      </a-row>
    </template>

    <a-result
      v-else
      status="403"
      title="仅具备档案维护权限的账号可维护档案主数据"
      sub-title="请联系管理员分配档案维护权限，或返回档案检索页查看当前已授权数据。"
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
import { computed, reactive, ref, watch } from "vue"
import { message } from "ant-design-vue"
import type { SelectProps } from "ant-design-vue"
import { RouterLink, useRoute, useRouter } from "vue-router"

import {
  createArchiveRecord,
  fetchArchiveDetail,
  fetchArchiveLocations,
  updateArchiveRecord,
  type ArchiveRecordDetail,
  type ArchiveRecordPayload,
} from "@/api/archives"
import { fetchDepartments } from "@/api/organizations"
import { useAuthStore } from "@/stores/auth"
import { ARCHIVE_MANAGER_FALLBACK_ROLES, profileHasAnyPermission } from "@/utils/access"

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const submitting = ref(false)
const optionsLoading = ref(false)
const archiveLoading = ref(false)
const departmentOptions = ref<SelectProps["options"]>([])
const locationOptions = ref<SelectProps["options"]>([])
const originalArchive = ref<ArchiveRecordDetail | null>(null)

const requiredRules = [{ required: true, message: "该字段不能为空。" }]
const yearRules = [
  { required: true, message: "年度不能为空。" },
  { type: "number" as const, min: 1000, max: 9999, message: "年度必须为四位数字。" },
]

const securityOptions = [
  { value: "PUBLIC", label: "公开" },
  { value: "INTERNAL", label: "内部" },
  { value: "SECRET", label: "秘密" },
  { value: "CONFIDENTIAL", label: "机密" },
  { value: "TOP_SECRET", label: "绝密" },
]

const retentionOptions = [
  { value: "永久", label: "永久" },
  { value: "长期", label: "长期" },
  { value: "30年", label: "30年" },
  { value: "10年", label: "10年" },
]

const archiveId = computed(() => {
  const rawValue = route.params.archiveId
  const parsedValue = Number(rawValue)
  return Number.isInteger(parsedValue) && parsedValue > 0 ? parsedValue : null
})

const isEditMode = computed(() => archiveId.value !== null)
const canCreateArchives = computed(() =>
  profileHasAnyPermission(authStore.profile, ["button.archive.create"], ARCHIVE_MANAGER_FALLBACK_ROLES),
)
const canEditArchives = computed(() =>
  profileHasAnyPermission(authStore.profile, ["button.archive.edit"], ARCHIVE_MANAGER_FALLBACK_ROLES),
)
const canManageArchives = computed(() => (isEditMode.value ? canEditArchives.value : canCreateArchives.value))
const pageLoading = computed(() => optionsLoading.value || archiveLoading.value)
const formTitle = computed(() => (isEditMode.value ? "编辑档案主数据" : "档案入库表单"))
const submitButtonText = computed(() => (isEditMode.value ? "保存修改" : "保存档案"))
const guideTitle = computed(() => (isEditMode.value ? "编辑提示" : "录入提示"))
const guideItems = computed(() => {
  if (isEditMode.value) {
    return [
      "修改档号、题名、责任信息、摘要或实体位置后，系统会自动生成新的修订记录。",
      "若填写形成日期，其年份仍必须与年度一致，否则后端会拒绝保存。",
      "编辑不会改变档案当前业务状态，状态流转仍需在档案详情页中单独处理。",
      "建议在修订说明中记录本次变更原因，方便后续审计与版本追踪。",
      "保存成功后将返回档案检索页，便于继续查看明细或处理后续流转。",
    ]
  }
  return [
    "必填字段为档号、题名、年度、保管期限、密级。",
    "若填写形成日期，其年份必须与年度一致。",
    "责任部门默认采用当前登录用户所属部门，可按需切换。",
    "保存后会自动生成第一条编目修订记录，后续修改也会持续留痕。",
    "条码与二维码可在档案列表中按需生成，不会阻塞当前入库动作。",
  ]
})

const initialState = () => ({
  archive_code: "",
  title: "",
  year: new Date().getFullYear(),
  retention_period: undefined as string | undefined,
  security_level: undefined as string | undefined,
  responsible_dept_id: authStore.profile?.dept_id,
  responsible_person: "",
  formed_at: "",
  keywords: "",
  summary: "",
  page_count: undefined as number | undefined,
  carrier_type: "",
  location_id: undefined as number | undefined,
  revision_remark: "",
})

const formState = reactive(initialState())

function applyArchiveToForm(archive: ArchiveRecordDetail) {
  formState.archive_code = archive.archive_code
  formState.title = archive.title
  formState.year = archive.year
  formState.retention_period = archive.retention_period
  formState.security_level = archive.security_level
  formState.responsible_dept_id = archive.responsible_dept_id ?? undefined
  formState.responsible_person = archive.responsible_person || ""
  formState.formed_at = archive.formed_at || ""
  formState.keywords = archive.keywords || ""
  formState.summary = archive.summary || ""
  formState.page_count = archive.page_count ?? undefined
  formState.carrier_type = archive.carrier_type || ""
  formState.location_id = archive.location_id ?? undefined
  formState.revision_remark = ""
}

function resetToCreateState() {
  Object.assign(formState, initialState())
}

function handleReset() {
  if (isEditMode.value && originalArchive.value) {
    applyArchiveToForm(originalArchive.value)
    return
  }
  resetToCreateState()
}

function filterOption(input: string, option?: { label?: unknown }) {
  return String(option?.label || "").toLowerCase().includes(input.toLowerCase())
}

async function loadOptions() {
  optionsLoading.value = true
  try {
    const [departmentsResponse, locationsResponse] = await Promise.all([
      fetchDepartments(),
      fetchArchiveLocations(),
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
    handleRequestError(error, "加载基础选项失败。")
  } finally {
    optionsLoading.value = false
  }
}

async function loadArchive() {
  if (!archiveId.value) {
    originalArchive.value = null
    resetToCreateState()
    return
  }

  archiveLoading.value = true
  try {
    const response = await fetchArchiveDetail(archiveId.value)
    originalArchive.value = response.data
    applyArchiveToForm(response.data)
  } catch (error) {
    handleRequestError(error, "加载档案详情失败。")
    await router.push("/archives/records")
  } finally {
    archiveLoading.value = false
  }
}

function buildPayload(): ArchiveRecordPayload {
  return {
    archive_code: formState.archive_code.trim(),
    title: formState.title.trim(),
    year: Number(formState.year),
    retention_period: formState.retention_period || "",
    security_level: formState.security_level || "",
    responsible_dept_id: formState.responsible_dept_id || undefined,
    responsible_person: formState.responsible_person.trim() || undefined,
    formed_at: formState.formed_at.trim() || undefined,
    keywords: formState.keywords.trim() || undefined,
    summary: formState.summary.trim() || undefined,
    page_count: formState.page_count || undefined,
    carrier_type: formState.carrier_type.trim() || undefined,
    location_id: formState.location_id || undefined,
    revision_remark: formState.revision_remark.trim() || undefined,
  }
}

async function handleSubmit() {
  const payload = buildPayload()

  submitting.value = true
  try {
    const response = isEditMode.value && archiveId.value
      ? await updateArchiveRecord(archiveId.value, payload)
      : await createArchiveRecord(payload)
    message.success(response.message)
    await router.push("/archives/records")
  } catch (error) {
    handleRequestError(error, isEditMode.value ? "更新档案失败。" : "创建档案失败。")
  } finally {
    submitting.value = false
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

watch(
  () => [route.params.archiveId, canManageArchives.value],
  async ([, canManage]) => {
    if (!canManage) {
      originalArchive.value = null
      departmentOptions.value = []
      locationOptions.value = []
      resetToCreateState()
      return
    }
    await loadOptions()
    await loadArchive()
  },
  { immediate: true },
)
</script>

<style scoped>
.create-page {
  display: grid;
}

.create-card,
.guide-card {
  border-radius: 24px;
}

.form-alert {
  margin-bottom: 16px;
}

.full-width {
  width: 100%;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.guide-list {
  margin: 0;
  padding-left: 20px;
  color: #475467;
  line-height: 1.9;
}

@media (max-width: 768px) {
  .form-actions {
    flex-direction: column-reverse;
    align-items: stretch;
  }
}
</style>
