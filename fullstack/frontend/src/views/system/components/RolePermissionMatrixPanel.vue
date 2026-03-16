<template>
  <a-card :bordered="false" class="matrix-card">
    <template #title>角色-菜单-按钮矩阵</template>
    <template #extra>
      <a-tag color="processing">{{ comparedRoles.length }} 个角色对比中</a-tag>
    </template>

    <a-alert
      class="matrix-alert"
      show-icon
      type="info"
      message="按权限码横向比对角色在菜单、按钮和接口层面的授权差异，可直接发现菜单可见但按钮缺失、或不同角色配置不一致的问题。"
    />

    <div class="matrix-toolbar">
      <a-input-search
        v-model:value="keyword"
        allow-clear
        class="matrix-search"
        placeholder="按权限名称、编码或模块筛选"
      />

      <a-select v-model:value="selectedModuleName" class="toolbar-select" :options="moduleOptions" />
      <a-select v-model:value="selectedPermissionType" class="toolbar-select" :options="permissionTypeOptions" />
      <a-select
        v-model:value="selectedRoleIds"
        mode="multiple"
        class="matrix-role-select"
        :max-tag-count="'responsive'"
        :options="roleOptions"
        placeholder="选择需要对比的角色"
        option-filter-prop="label"
        show-search
      />

      <a-switch
        v-model:checked="differenceOnly"
        :disabled="comparedRoles.length < 2"
        checked-children="仅差异"
        un-checked-children="全部"
      />
    </div>

    <div class="matrix-summary-grid">
      <div class="summary-box">
        <span>当前可见权限</span>
        <strong>{{ filteredMatrixRows.length }}</strong>
        <small>已按筛选条件裁剪后的权限项数量</small>
      </div>
      <div class="summary-box">
        <span>存在差异项</span>
        <strong>{{ differenceRowCount }}</strong>
        <small>至少一个角色有权限、至少一个角色无权限</small>
      </div>
      <div class="summary-box">
        <span>全部具备</span>
        <strong>{{ fullyAssignedRowCount }}</strong>
        <small>当前对比角色均具备的权限项数量</small>
      </div>
      <div class="summary-box">
        <span>全部缺失</span>
        <strong>{{ fullyUnassignedRowCount }}</strong>
        <small>当前对比角色均未配置的权限项数量</small>
      </div>
    </div>

    <div v-if="comparedRoles.length" class="role-chip-list">
      <span class="role-chip-label">当前对比角色</span>
      <a-tag v-for="role in comparedRoles" :key="role.id" :color="role.status ? 'blue' : 'default'">
        {{ role.role_name }} / {{ role.role_code }}
      </a-tag>
    </div>

    <a-table
      :columns="matrixColumns"
      :data-source="filteredMatrixRows"
      :loading="loading"
      row-key="id"
      :pagination="{ pageSize: 10, showSizeChanger: false }"
      :scroll="{ x: 'max-content' }"
    >
      <template #emptyText>
        <a-empty description="当前筛选条件下暂无可展示的权限矩阵" />
      </template>

      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'permission'">
          <div class="permission-cell">
            <strong>{{ record.permission_name }}</strong>
            <span>{{ record.permission_code }}</span>
          </div>
        </template>

        <template v-else-if="column.key === 'permission_type'">
          <a-tag :color="permissionTypeColorMap[record.permission_type] || 'default'">
            {{ permissionTypeLabelMap[record.permission_type] || record.permission_type }}
          </a-tag>
        </template>

        <template v-else-if="column.key === 'module_name'">
          {{ record.module_label }}
        </template>

        <template v-else-if="column.key === 'assigned_count'">
          <span class="assigned-count">{{ record.assigned_count }}/{{ comparedRoles.length }}</span>
        </template>

        <template v-else-if="String(column.key).startsWith('role-')">
          <a-tag :color="record.role_state_map[String(column.key)] ? 'green' : 'default'">
            {{ record.role_state_map[String(column.key)] ? "可用" : "缺失" }}
          </a-tag>
        </template>
      </template>
    </a-table>
  </a-card>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue"

import type { RoleItem, SystemPermissionItem } from "@/api/accounts"

interface MatrixRowItem {
  id: number
  permission_name: string
  permission_code: string
  permission_type: string
  module_name: string
  module_label: string
  sort_order: number
  assigned_count: number
  role_state_map: Record<string, boolean>
}

const permissionTypeLabelMap: Record<string, string> = {
  MENU: "菜单",
  BUTTON: "按钮",
  API: "接口",
}

const permissionTypeColorMap: Record<string, string> = {
  MENU: "blue",
  BUTTON: "purple",
  API: "cyan",
}

const permissionModuleLabelMap: Record<string, string> = {
  dashboard: "工作台",
  archives: "档案业务",
  digitization: "数字化",
  borrowing: "借阅业务",
  notifications: "通知中心",
  destruction: "销毁业务",
  reports: "报表中心",
  audit: "审计监管",
  system: "系统配置",
}

const props = defineProps<{
  roles: RoleItem[]
  permissions: SystemPermissionItem[]
  loading?: boolean
}>()

const keyword = ref("")
const selectedModuleName = ref("all")
const selectedPermissionType = ref("all")
const selectedRoleIds = ref<number[]>([])
const differenceOnly = ref(false)

const roleOptions = computed(() =>
  props.roles.map((item) => ({
    value: item.id,
    label: `${item.role_name}（${item.role_code}${item.status ? "" : " / 已停用"}）`,
  })),
)

const defaultSelectedRoleIds = computed(() => {
  const activeRoleIds = props.roles.filter((item) => item.status).map((item) => item.id)
  const candidateIds = activeRoleIds.length ? activeRoleIds : props.roles.map((item) => item.id)
  return candidateIds.slice(0, 6)
})

watch(
  () => props.roles,
  (currentRoles) => {
    const validRoleIdSet = new Set(currentRoles.map((item) => item.id))
    const preservedRoleIds = selectedRoleIds.value.filter((roleId) => validRoleIdSet.has(roleId))

    if (preservedRoleIds.length) {
      selectedRoleIds.value = preservedRoleIds
      return
    }

    selectedRoleIds.value = [...defaultSelectedRoleIds.value]
  },
  { immediate: true, deep: true },
)

const comparedRoles = computed(() => {
  const selectedRoleIdSet = new Set(selectedRoleIds.value)
  const baseRoles = props.roles.filter((item) => selectedRoleIdSet.has(item.id))
  return baseRoles.sort((left, right) => Number(right.status) - Number(left.status) || left.id - right.id)
})

const moduleOptions = computed(() => {
  const moduleNameList = [...new Set(props.permissions.filter((item) => item.status).map((item) => item.module_name))]
  return [
    { value: "all", label: "全部模块" },
    ...moduleNameList.map((moduleName) => ({
      value: moduleName,
      label: permissionModuleLabelMap[moduleName] || moduleName,
    })),
  ]
})

const permissionTypeOptions = [
  { value: "all", label: "全部类型" },
  { value: "MENU", label: "菜单" },
  { value: "BUTTON", label: "按钮" },
  { value: "API", label: "接口" },
]

const rolePermissionCodeMap = computed(() => {
  const roleMap = new Map<number, Set<string>>()

  props.roles.forEach((role) => {
    roleMap.set(
      role.id,
      new Set(role.permissions.filter((item) => item.status).map((item) => item.permission_code)),
    )
  })

  return roleMap
})

const matrixRows = computed<MatrixRowItem[]>(() =>
  props.permissions
    .filter((item) => item.status)
    .sort((left, right) => left.sort_order - right.sort_order || left.id - right.id)
    .map((permission) => {
      const roleStateMap: Record<string, boolean> = {}
      let assignedCount = 0

      comparedRoles.value.forEach((role) => {
        const hasPermission = rolePermissionCodeMap.value.get(role.id)?.has(permission.permission_code) ?? false
        roleStateMap[`role-${role.id}`] = hasPermission
        if (hasPermission) {
          assignedCount += 1
        }
      })

      return {
        id: permission.id,
        permission_name: permission.permission_name,
        permission_code: permission.permission_code,
        permission_type: permission.permission_type,
        module_name: permission.module_name,
        module_label: permissionModuleLabelMap[permission.module_name] || permission.module_name,
        sort_order: permission.sort_order,
        assigned_count: assignedCount,
        role_state_map: roleStateMap,
      }
    }),
)

const filteredMatrixRows = computed(() => {
  const normalizedKeyword = keyword.value.trim().toLowerCase()

  return matrixRows.value.filter((item) => {
    if (selectedModuleName.value !== "all" && item.module_name !== selectedModuleName.value) {
      return false
    }

    if (selectedPermissionType.value !== "all" && item.permission_type !== selectedPermissionType.value) {
      return false
    }

    if (
      normalizedKeyword
      && ![item.permission_name, item.permission_code, item.module_label]
        .some((field) => field.toLowerCase().includes(normalizedKeyword))
    ) {
      return false
    }

    if (differenceOnly.value && comparedRoles.value.length > 1) {
      return item.assigned_count > 0 && item.assigned_count < comparedRoles.value.length
    }

    return true
  })
})

const differenceRowCount = computed(
  () => matrixRows.value.filter((item) => item.assigned_count > 0 && item.assigned_count < comparedRoles.value.length).length,
)

const fullyAssignedRowCount = computed(
  () => matrixRows.value.filter((item) => comparedRoles.value.length > 0 && item.assigned_count === comparedRoles.value.length).length,
)

const fullyUnassignedRowCount = computed(
  () => matrixRows.value.filter((item) => item.assigned_count === 0).length,
)

const matrixColumns = computed(() => [
  { title: "权限", key: "permission", width: 280, fixed: "left" as const },
  { title: "类型", key: "permission_type", width: 100, fixed: "left" as const },
  { title: "模块", key: "module_name", width: 140, fixed: "left" as const },
  { title: "已授权角色", key: "assigned_count", width: 120 },
  ...comparedRoles.value.map((role) => ({
    title: role.role_name,
    key: `role-${role.id}`,
    width: 130,
  })),
])
</script>

<style scoped>
.matrix-card {
  border-radius: 24px;
}

.matrix-alert {
  margin-bottom: 18px;
}

.matrix-toolbar {
  display: grid;
  grid-template-columns: minmax(240px, 1.4fr) repeat(2, minmax(140px, 180px)) minmax(260px, 1.2fr) auto;
  gap: 12px;
  margin-bottom: 18px;
}

.matrix-search,
.toolbar-select,
.matrix-role-select {
  width: 100%;
}

.matrix-summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.summary-box {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(15, 23, 42, 0.04);
}

.summary-box span,
.summary-box small,
.permission-cell span {
  color: #667085;
}

.summary-box strong {
  font-size: 22px;
  line-height: 1.2;
}

.role-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 18px;
}

.role-chip-label,
.assigned-count {
  color: #475467;
}

.permission-cell {
  display: grid;
  gap: 4px;
}

@media (max-width: 1080px) {
  .matrix-toolbar {
    grid-template-columns: 1fr;
  }
}
</style>
