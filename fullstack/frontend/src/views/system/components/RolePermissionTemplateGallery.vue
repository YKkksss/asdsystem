<template>
  <a-card :bordered="false" class="insight-card">
    <template #title>默认角色模板预览</template>
    <template #extra>
      <a-tag color="processing">{{ templateCards.length }} 套模板</a-tag>
    </template>

    <a-alert
      class="insight-alert"
      show-icon
      type="info"
      message="用于预览系统内置角色模板与当前角色实际授权的贴合度，便于确认默认菜单与按钮边界是否已经落地。"
    />

    <a-spin :spinning="loading">
      <div v-if="templateCards.length" class="template-grid">
        <article v-for="item in templateCards" :key="item.template_key" class="template-card">
          <div class="template-header">
            <div class="template-title-block">
              <strong>{{ item.template_name }}</strong>
              <span>{{ item.role_name }} / {{ item.role_code }}</span>
            </div>

            <a-tag :color="item.status_color">
              {{ item.status_label }}
            </a-tag>
          </div>

          <p class="template-description">
            {{ item.description || "当前模板未填写说明，可在角色配置中补充职责边界描述。" }}
          </p>

          <div class="template-metrics">
            <div class="metric-item">
              <strong>{{ item.resolved_count }}</strong>
              <span>模板权限</span>
            </div>
            <div class="metric-item">
              <strong>{{ item.menu_count }}</strong>
              <span>菜单</span>
            </div>
            <div class="metric-item">
              <strong>{{ item.button_count }}</strong>
              <span>按钮</span>
            </div>
            <div class="metric-item">
              <strong>{{ item.api_count }}</strong>
              <span>接口</span>
            </div>
          </div>

          <div class="template-progress-block">
            <template v-if="item.role_exists">
              <div class="template-progress-header">
                <span>当前角色落地进度</span>
                <strong>{{ item.matched_count }}/{{ item.resolved_count || item.matched_count }}</strong>
              </div>
              <a-progress
                :percent="item.resolved_count ? Math.round((item.matched_count / item.resolved_count) * 100) : 100"
                size="small"
                :stroke-color="item.status_color === 'success' ? '#0a7152' : '#d97706'"
                :show-info="false"
              />
              <small>
                缺少 {{ item.missing_count }} 项，额外 {{ item.extra_count }} 项
                <span v-if="!item.role_status" class="status-note">，当前角色已停用</span>
              </small>
            </template>
            <small v-else>当前系统中尚未创建同编码角色，可直接参考此模板创建或补齐授权。</small>
          </div>

          <div class="module-tag-list">
            <a-tag v-for="moduleLabel in item.module_labels.slice(0, 6)" :key="moduleLabel">
              {{ moduleLabel }}
            </a-tag>
            <a-tag v-if="item.module_labels.length > 6">+{{ item.module_labels.length - 6 }}</a-tag>
          </div>
        </article>
      </div>

      <a-empty v-else description="暂无默认权限模板" />
    </a-spin>
  </a-card>
</template>

<script setup lang="ts">
import { computed } from "vue"

import type { PermissionTemplateItem, RoleItem, SystemPermissionItem } from "@/api/accounts"

interface TemplateCardItem {
  template_key: string
  role_code: string
  role_name: string
  template_name: string
  description: string
  resolved_count: number
  matched_count: number
  missing_count: number
  extra_count: number
  menu_count: number
  button_count: number
  api_count: number
  module_labels: string[]
  role_exists: boolean
  role_status: boolean
  status_label: string
  status_color: string
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
  templates: PermissionTemplateItem[]
  permissions: SystemPermissionItem[]
  roles: RoleItem[]
  loading?: boolean
}>()

const availablePermissionByCode = computed(
  () =>
    new Map(
      props.permissions
        .filter((item) => item.status)
        .map((item) => [item.permission_code, item] as const),
    ),
)

const roleByCode = computed(() => new Map(props.roles.map((item) => [item.role_code, item] as const)))

const templateCards = computed<TemplateCardItem[]>(() =>
  props.templates.map((template) => {
    const resolvedPermissions = template.permission_codes
      .map((permissionCode) => availablePermissionByCode.value.get(permissionCode))
      .filter((permission): permission is SystemPermissionItem => Boolean(permission))
    const resolvedPermissionCodeSet = new Set(resolvedPermissions.map((item) => item.permission_code))
    const matchedRole = roleByCode.value.get(template.role_code)
    const matchedRolePermissionCodeSet = new Set(
      (matchedRole?.permissions || [])
        .filter((item) => item.status)
        .map((item) => item.permission_code),
    )

    const matchedCount = [...resolvedPermissionCodeSet].filter((permissionCode) =>
      matchedRolePermissionCodeSet.has(permissionCode),
    ).length
    const missingCount = [...resolvedPermissionCodeSet].filter(
      (permissionCode) => !matchedRolePermissionCodeSet.has(permissionCode),
    ).length
    const extraCount = [...matchedRolePermissionCodeSet].filter(
      (permissionCode) => !resolvedPermissionCodeSet.has(permissionCode),
    ).length
    const moduleLabels = [...new Set(resolvedPermissions.map((item) => permissionModuleLabelMap[item.module_name] || item.module_name))]

    let statusLabel = "待落地"
    let statusColor = "default"

    if (matchedRole) {
      if (!missingCount && !extraCount) {
        statusLabel = "与模板一致"
        statusColor = "success"
      } else {
        statusLabel = "与模板有偏差"
        statusColor = "warning"
      }
    }

    return {
      template_key: template.template_key,
      role_code: template.role_code,
      role_name: template.role_name,
      template_name: template.template_name,
      description: template.description,
      resolved_count: resolvedPermissions.length,
      matched_count: matchedCount,
      missing_count: missingCount,
      extra_count: extraCount,
      menu_count: resolvedPermissions.filter((item) => item.permission_type === "MENU").length,
      button_count: resolvedPermissions.filter((item) => item.permission_type === "BUTTON").length,
      api_count: resolvedPermissions.filter((item) => item.permission_type === "API").length,
      module_labels: moduleLabels,
      role_exists: Boolean(matchedRole),
      role_status: matchedRole?.status ?? false,
      status_label: statusLabel,
      status_color: statusColor,
    }
  }),
)
</script>

<style scoped>
.insight-card {
  border-radius: 24px;
}

.insight-alert {
  margin-bottom: 18px;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}

.template-card {
  display: grid;
  gap: 16px;
  padding: 18px;
  border: 1px solid rgba(16, 24, 40, 0.08);
  border-radius: 22px;
  background:
    radial-gradient(circle at top right, rgba(10, 113, 82, 0.08), transparent 38%),
    #ffffff;
}

.template-header,
.template-progress-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.template-title-block,
.template-progress-block {
  display: grid;
  gap: 6px;
}

.template-title-block span,
.template-description,
.template-progress-block small,
.metric-item span,
.status-note {
  color: #667085;
}

.template-description {
  margin: 0;
  min-height: 44px;
  line-height: 1.7;
}

.template-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.metric-item {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.04);
}

.metric-item strong {
  font-size: 18px;
  line-height: 1.2;
}

.module-tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 720px) {
  .template-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
