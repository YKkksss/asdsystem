<template>
  <section class="location-page">
    <template v-if="canManageArchives">
      <a-row :gutter="[20, 20]">
        <a-col :xs="24" :xl="15">
          <a-card :bordered="false" class="location-card">
            <div class="toolbar">
              <a-input-search
                v-model:value="search"
                allow-clear
                placeholder="按库房、柜号、盒号或完整编码搜索"
                @search="loadLocations"
              />
              <a-button @click="loadLocations">刷新</a-button>
            </div>

            <a-table
              :columns="columns"
              :data-source="locations"
              :loading="loading"
              row-key="id"
              :pagination="{ pageSize: 8, showSizeChanger: false }"
            >
              <template #emptyText>
                <a-empty description="暂无实体位置" />
              </template>

              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'full_location_code'">
                  <div class="location-code-cell">
                    <strong>{{ record.full_location_code }}</strong>
                    <span>{{ record.warehouse_name }} · {{ record.cabinet_code }} 柜</span>
                  </div>
                </template>

                <template v-else-if="column.key === 'status'">
                  <a-tag :color="record.status ? 'green' : 'default'">
                    {{ record.status ? "可用" : "停用" }}
                  </a-tag>
                </template>

                <template v-else-if="column.key === 'actions'">
                  <a-button type="link" @click="handleEdit(record)">编辑</a-button>
                </template>
              </template>
            </a-table>
          </a-card>
        </a-col>

        <a-col :xs="24" :xl="9">
          <a-card :bordered="false" class="location-card">
            <template #title>{{ formTitle }}</template>

            <a-alert
              v-if="isEditMode"
              class="form-alert"
              type="info"
              show-icon
              message="当前为实体位置编辑模式，保存后系统会自动刷新完整位置编码。"
            />

            <a-form
              :model="formState"
              layout="vertical"
              @finish="handleSubmit"
            >
              <a-form-item label="库房名称" name="warehouse_name" :rules="requiredRules">
                <a-input v-model:value="formState.warehouse_name" placeholder="例如：一号库房" />
              </a-form-item>
              <a-form-item label="分区名称">
                <a-input v-model:value="formState.area_name" placeholder="例如：A区" />
              </a-form-item>
              <a-row :gutter="[12, 0]">
                <a-col :span="12">
                  <a-form-item label="柜号" name="cabinet_code" :rules="requiredRules">
                    <a-input v-model:value="formState.cabinet_code" placeholder="G01" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="架号" name="rack_code" :rules="requiredRules">
                    <a-input v-model:value="formState.rack_code" placeholder="J01" />
                  </a-form-item>
                </a-col>
              </a-row>
              <a-row :gutter="[12, 0]">
                <a-col :span="12">
                  <a-form-item label="层号" name="layer_code" :rules="requiredRules">
                    <a-input v-model:value="formState.layer_code" placeholder="L01" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="盒号" name="box_code" :rules="requiredRules">
                    <a-input v-model:value="formState.box_code" placeholder="H01" />
                  </a-form-item>
                </a-col>
              </a-row>
              <a-form-item label="备注">
                <a-textarea v-model:value="formState.remark" :rows="3" placeholder="可填写适用说明或库位备注" />
              </a-form-item>
              <a-form-item label="状态">
                <a-switch v-model:checked="formState.status" checked-children="可用" un-checked-children="停用" />
              </a-form-item>

              <div class="location-actions">
                <a-button v-if="isEditMode" @click="cancelEditing">返回新增</a-button>
                <a-button @click="handleReset">{{ resetButtonText }}</a-button>
                <a-button html-type="submit" type="primary" :loading="submitting">{{ submitButtonText }}</a-button>
              </div>
            </a-form>
          </a-card>
        </a-col>
      </a-row>
    </template>

    <a-result
      v-else
      status="403"
      title="仅档案管理员可维护实体位置"
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
import { RouterLink } from "vue-router"

import {
  type ArchiveLocationPayload,
  createArchiveLocation,
  fetchArchiveLocations,
  updateArchiveLocation,
  type ArchiveStorageLocation,
} from "@/api/archives"
import { useAuthStore } from "@/stores/auth"

const columns = [
  { title: "完整位置编码", key: "full_location_code" },
  { title: "分区", dataIndex: "area_name", key: "area_name", width: 120 },
  { title: "盒号", dataIndex: "box_code", key: "box_code", width: 120 },
  { title: "状态", key: "status", width: 100 },
  { title: "操作", key: "actions", width: 120 },
]

const requiredRules = [{ required: true, message: "该字段不能为空。" }]

const authStore = useAuthStore()
const loading = ref(false)
const submitting = ref(false)
const search = ref("")
const locations = ref<ArchiveStorageLocation[]>([])
const editingLocationId = ref<number | null>(null)
const editingLocationSnapshot = ref<ArchiveStorageLocation | null>(null)

const canManageArchives = computed(() =>
  Boolean(authStore.profile?.roles.some((role) => ["ADMIN", "ARCHIVIST"].includes(role.role_code))),
)

const isEditMode = computed(() => editingLocationId.value !== null)
const formTitle = computed(() => (isEditMode.value ? "编辑实体位置" : "新增实体位置"))
const submitButtonText = computed(() => (isEditMode.value ? "保存修改" : "保存位置"))
const resetButtonText = computed(() => (isEditMode.value ? "恢复原值" : "重置"))

const initialState = () => ({
  warehouse_name: "",
  area_name: "",
  cabinet_code: "",
  rack_code: "",
  layer_code: "",
  box_code: "",
  status: true,
  remark: "",
})

const formState = reactive(initialState())

function applyLocationToForm(location: ArchiveStorageLocation) {
  formState.warehouse_name = location.warehouse_name
  formState.area_name = location.area_name || ""
  formState.cabinet_code = location.cabinet_code
  formState.rack_code = location.rack_code
  formState.layer_code = location.layer_code
  formState.box_code = location.box_code
  formState.status = location.status
  formState.remark = location.remark || ""
}

function resetToCreateState() {
  editingLocationId.value = null
  editingLocationSnapshot.value = null
  Object.assign(formState, initialState())
}

function handleReset() {
  if (isEditMode.value && editingLocationSnapshot.value) {
    applyLocationToForm(editingLocationSnapshot.value)
    return
  }
  resetToCreateState()
}

function cancelEditing() {
  resetToCreateState()
}

function handleEdit(location: ArchiveStorageLocation) {
  editingLocationId.value = location.id
  editingLocationSnapshot.value = { ...location }
  applyLocationToForm(location)
}

async function loadLocations() {
  loading.value = true
  try {
    const response = await fetchArchiveLocations({
      search: search.value || undefined,
    })
    locations.value = response.data
  } catch (error) {
    handleRequestError(error, "加载实体位置失败。")
  } finally {
    loading.value = false
  }
}

function buildPayload(): ArchiveLocationPayload {
  return {
    warehouse_name: formState.warehouse_name.trim(),
    area_name: formState.area_name.trim() || undefined,
    cabinet_code: formState.cabinet_code.trim(),
    rack_code: formState.rack_code.trim(),
    layer_code: formState.layer_code.trim(),
    box_code: formState.box_code.trim(),
    status: formState.status,
    remark: formState.remark.trim() || undefined,
  }
}

async function handleSubmit() {
  const payload = buildPayload()
  submitting.value = true
  try {
    const response = isEditMode.value && editingLocationId.value
      ? await updateArchiveLocation(editingLocationId.value, payload)
      : await createArchiveLocation(payload)
    message.success(response.message)
    resetToCreateState()
    await loadLocations()
  } catch (error) {
    handleRequestError(error, isEditMode.value ? "更新实体位置失败。" : "创建实体位置失败。")
  } finally {
    submitting.value = false
  }
}

function handleRequestError(error: unknown, fallbackMessage: string) {
  if (typeof error === "object" && error !== null && "response" in error) {
    const response = (error as { response?: { data?: { message?: string }; status?: number } }).response
    if (response?.status === 403) {
      message.error("当前账号无权维护实体位置。")
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
      locations.value = []
      resetToCreateState()
      return
    }
    void loadLocations()
  },
  { immediate: true },
)
</script>

<style scoped>
.location-page {
  display: grid;
}

.location-card {
  border-radius: 24px;
}

.form-alert {
  margin-bottom: 16px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.location-code-cell {
  display: grid;
  gap: 6px;
}

.location-code-cell span {
  color: #667085;
  font-size: 12px;
}

.location-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 768px) {
  .toolbar,
  .location-actions {
    flex-direction: column;
  }
}
</style>
