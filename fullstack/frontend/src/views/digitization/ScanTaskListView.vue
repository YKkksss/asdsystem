<template>
  <section class="scan-page">
    <template v-if="canManageArchives">
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
            <div class="toolbar">
              <a-button @click="loadTasks">刷新任务</a-button>
            </div>

            <a-table
              :columns="columns"
              :data-source="tasks"
              :loading="loading"
              row-key="id"
              :pagination="{ pageSize: 8, showSizeChanger: false }"
            >
              <template #emptyText>
                <a-empty description="暂无扫描任务" />
              </template>

              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'task_name'">
                  <div class="task-title-cell">
                    <strong>{{ record.task_name }}</strong>
                    <span>{{ record.task_no }}</span>
                  </div>
                </template>

                <template v-else-if="column.key === 'status'">
                  <a-tag :color="statusColorMap[record.status] || 'default'">
                    {{ statusLabelMap[record.status] || record.status }}
                  </a-tag>
                </template>

                <template v-else-if="column.key === 'progress'">
                  <span>{{ record.completed_count }}/{{ record.total_count }}</span>
                </template>

                <template v-else-if="column.key === 'actions'">
                  <RouterLink :to="`/digitization/scan-tasks/${record.id}`">
                    <a-button type="link">查看详情</a-button>
                  </RouterLink>
                </template>
              </template>
            </a-table>
          </a-card>
        </a-col>

        <a-col :xs="24" :xl="9">
          <a-card :bordered="false" class="panel-card">
            <template #title>新建扫描任务</template>

            <a-form :model="formState" layout="vertical" @finish="handleCreateTask">
              <a-form-item label="任务名称" name="task_name" :rules="requiredRules">
                <a-input v-model:value="formState.task_name" placeholder="例如：第一批纸档数字化任务" />
              </a-form-item>

              <a-form-item label="执行人" name="assigned_user_id" :rules="requiredRules">
                <a-select
                  v-model:value="formState.assigned_user_id"
                  placeholder="请选择执行人"
                  :options="assigneeOptions"
                  :loading="optionsLoading"
                />
              </a-form-item>

              <a-form-item label="档案选择" name="archive_ids" :rules="archiveRules">
                <a-select
                  v-model:value="formState.archive_ids"
                  mode="multiple"
                  placeholder="选择待扫描档案"
                  :options="archiveOptions"
                  :loading="optionsLoading"
                  show-search
                  :filter-option="filterOption"
                />
              </a-form-item>

              <a-form-item label="备注">
                <a-textarea
                  v-model:value="formState.remark"
                  :rows="3"
                  placeholder="可填写扫描批次说明、来源范围等"
                />
              </a-form-item>

              <div class="form-actions">
                <a-button @click="handleReset">重置</a-button>
                <a-button html-type="submit" type="primary" :loading="submitting">创建任务</a-button>
              </div>
            </a-form>
          </a-card>
        </a-col>
      </a-row>
    </template>

    <a-result
      v-else
      status="403"
      title="仅档案管理员可维护扫描任务"
      sub-title="请使用管理员或档案员账号登录，或返回档案检索页查看已授权数据。"
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
import { RouterLink, useRouter } from "vue-router"

import { fetchArchives } from "@/api/archives"
import {
  createScanTask,
  fetchScanTaskAssignees,
  fetchScanTasks,
  type ScanTask,
} from "@/api/digitization"
import { useAuthStore } from "@/stores/auth"

const router = useRouter()
const authStore = useAuthStore()

const canManageArchives = computed(() =>
  Boolean(authStore.profile?.roles.some((role) => ["ADMIN", "ARCHIVIST"].includes(role.role_code))),
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

const loading = ref(false)
const optionsLoading = ref(false)
const submitting = ref(false)
const tasks = ref<ScanTask[]>([])
const assigneeOptions = ref<SelectProps["options"]>([])
const archiveOptions = ref<SelectProps["options"]>([])

const requiredRules = [{ required: true, message: "该字段不能为空。" }]
const archiveRules = [{ required: true, type: "array" as const, min: 1, message: "至少选择一份档案。" }]

const columns = [
  { title: "任务信息", key: "task_name" },
  { title: "执行人", dataIndex: "assigned_user_name", key: "assigned_user_name", width: 120 },
  { title: "状态", key: "status", width: 110 },
  { title: "进度", key: "progress", width: 100 },
  { title: "失败数", dataIndex: "failed_count", key: "failed_count", width: 90 },
  { title: "操作", key: "actions", width: 120 },
]

const initialState = () => ({
  task_name: "",
  assigned_user_id: authStore.profile?.id,
  archive_ids: [] as number[],
  remark: "",
})

const formState = reactive(initialState())

const summaryCards = computed(() => {
  const total = tasks.value.length
  const inProgress = tasks.value.filter((item) => item.status === "IN_PROGRESS").length
  const completed = tasks.value.filter((item) => item.status === "COMPLETED").length
  const failed = tasks.value.filter((item) => item.status === "FAILED").length
  return [
    { label: "任务总量", value: total, caption: "当前系统中的扫描任务总数" },
    { label: "进行中", value: inProgress, caption: "已开始但尚未全部完成的任务" },
    { label: "已完成", value: completed, caption: "全部明细已上传处理完成" },
    { label: "已失败", value: failed, caption: "存在异常文件或处理失败的任务" },
  ]
})

function filterOption(input: string, option?: { label?: unknown }) {
  return String(option?.label || "").toLowerCase().includes(input.toLowerCase())
}

function handleReset() {
  Object.assign(formState, initialState())
}

async function loadTasks() {
  loading.value = true
  try {
    const response = await fetchScanTasks()
    tasks.value = response.data
  } catch (error) {
    handleRequestError(error, "加载扫描任务失败。")
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  optionsLoading.value = true
  try {
    const [assigneesResponse, archivesResponse] = await Promise.all([
      fetchScanTaskAssignees(),
      fetchArchives(),
    ])
    assigneeOptions.value = assigneesResponse.data.map((item) => ({
      value: item.id,
      label: `${item.real_name}（${item.username}）`,
    }))
    archiveOptions.value = archivesResponse.data
      .filter((item) => ["DRAFT", "PENDING_SCAN"].includes(item.status))
      .map((item) => ({
        value: item.id,
        label: `${item.archive_code}｜${item.title}`,
      }))
  } catch (error) {
    handleRequestError(error, "加载扫描任务选项失败。")
  } finally {
    optionsLoading.value = false
  }
}

async function handleCreateTask() {
  submitting.value = true
  try {
    const response = await createScanTask({
      task_name: formState.task_name.trim(),
      assigned_user_id: formState.assigned_user_id || undefined,
      archive_ids: formState.archive_ids,
      remark: formState.remark.trim() || undefined,
    })
    message.success(response.message)
    handleReset()
    await loadTasks()
    await loadOptions()
    await router.push(`/digitization/scan-tasks/${response.data.id}`)
  } catch (error) {
    handleRequestError(error, "创建扫描任务失败。")
  } finally {
    submitting.value = false
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
  canManageArchives,
  (canManage) => {
    if (!canManage) {
      tasks.value = []
      assigneeOptions.value = []
      archiveOptions.value = []
      handleReset()
      return
    }
    void loadTasks()
    void loadOptions()
  },
  { immediate: true },
)
</script>

<style scoped>
.scan-page {
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
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(243, 247, 255, 0.92));
  box-shadow: 0 18px 40px rgba(24, 61, 110, 0.08);
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
  color: #155eef;
}

.summary-card small {
  color: #667085;
  line-height: 1.7;
}

.panel-card {
  border-radius: 24px;
}

.toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.task-title-cell {
  display: grid;
  gap: 6px;
}

.task-title-cell span {
  color: #667085;
  font-size: 12px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 768px) {
  .form-actions {
    flex-direction: column-reverse;
    align-items: stretch;
  }
}
</style>
