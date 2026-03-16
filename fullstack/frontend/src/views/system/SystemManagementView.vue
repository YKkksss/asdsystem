<template>
  <section class="system-page">
    <template v-if="canAccessSystemManagement">
      <div class="summary-grid">
        <a-card v-for="item in summaryCards" :key="item.label" :bordered="false" class="summary-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <small>{{ item.caption }}</small>
        </a-card>
      </div>

      <a-card :bordered="false" class="panel-card">
        <div class="page-header">
          <div>
            <strong>系统管理总览</strong>
            <p>统一维护用户、角色、组织架构与后端运行状态，便于管理员集中收口配置。</p>
          </div>

          <a-space wrap>
            <a-button :loading="healthLoading" @click="loadHealthData">刷新健康检查</a-button>
            <a-button
              type="primary"
              :loading="userLoading || roleLoading || permissionLoading || departmentLoading || healthLoading"
              @click="loadPageData"
            >
              刷新全部
            </a-button>
          </a-space>
        </div>

        <a-alert
          show-icon
          type="info"
          message="用户、角色和部门维护会直接影响登录权限、数据范围与审批负责人配置，请在变更前确认业务归属。"
        />
      </a-card>

      <a-card :bordered="false" class="panel-card">
        <a-tabs v-model:activeKey="activeTab">
          <a-tab-pane v-if="canManageUsers" key="users" tab="用户管理">
            <div class="tab-toolbar">
              <a-input-search
                v-model:value="userKeyword"
                allow-clear
                class="toolbar-search"
                placeholder="按账号、姓名、邮箱或部门筛选"
              />

              <a-space wrap>
                <a-button :loading="userLoading" @click="loadUsersData">刷新用户</a-button>
                <a-button v-if="canManageUsers" type="primary" @click="openCreateUser">新建用户</a-button>
              </a-space>
            </div>

            <a-table
              :columns="userColumns"
              :data-source="filteredUsers"
              :loading="userLoading"
              row-key="id"
              :row-class-name="getUserRowClassName"
              :pagination="{
                current: userPagination.current,
                pageSize: userPagination.pageSize,
                showSizeChanger: false,
                onChange: handleUserTableChange,
              }"
            >
              <template #emptyText>
                <a-empty description="暂无用户数据" />
              </template>

              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'user'">
                  <div class="user-cell">
                    <strong>{{ record.real_name }}</strong>
                    <span>{{ record.username }}</span>
                  </div>
                </template>

                <template v-else-if="column.key === 'roles'">
                  <a-space wrap>
                    <a-tag v-for="role in record.roles" :key="role.id" color="blue">
                      {{ role.role_name }}
                    </a-tag>
                    <span v-if="!record.roles.length" class="muted-text">未分配角色</span>
                  </a-space>
                </template>

                <template v-else-if="column.key === 'security_clearance_level'">
                  <a-tag color="gold">
                    {{ securityLabelMap[record.security_clearance_level] || record.security_clearance_level }}
                  </a-tag>
                </template>

                <template v-else-if="column.key === 'status'">
                  <a-tag :color="record.status ? 'green' : 'default'">
                    {{ record.status ? "启用" : "停用" }}
                  </a-tag>
                </template>

                <template v-else-if="column.key === 'lock_state'">
                  <div class="lock-cell">
                    <a-tag v-if="record.lock_until_at" color="red">
                      锁定至 {{ formatDateTime(record.lock_until_at) }}
                    </a-tag>
                    <a-tag v-else-if="record.failed_login_count > 0" color="orange">
                      已累计失败 {{ record.failed_login_count }} 次
                    </a-tag>
                    <span v-else class="muted-text">正常</span>
                  </div>
                </template>

                <template v-else-if="column.key === 'last_login_at'">
                  {{ formatDateTime(record.last_login_at) }}
                </template>

                <template v-else-if="column.key === 'actions'">
                  <a-space wrap>
                    <a-button v-if="canManageUsers" type="link" @click="openEditUser(record)">编辑</a-button>
                    <a-button
                      v-if="canManageUsers && (record.lock_until_at || record.failed_login_count > 0)"
                      type="link"
                      :loading="unlockingUserId === record.id"
                      @click="handleUnlockUser(record.id)"
                    >
                      解锁
                    </a-button>
                  </a-space>
                </template>
              </template>
            </a-table>
          </a-tab-pane>

          <a-tab-pane v-if="canManageRoles" key="roles" tab="角色管理">
            <div class="tab-toolbar">
              <a-input-search
                v-model:value="roleKeyword"
                allow-clear
                class="toolbar-search"
                placeholder="按角色编码、名称或数据范围筛选"
              />

              <a-space wrap>
                <a-button :loading="roleLoading" @click="loadRolesData">刷新角色</a-button>
                <a-button v-if="canManageRoles" type="primary" @click="openCreateRole">新建角色</a-button>
              </a-space>
            </div>

            <div class="role-insight-stack">
              <RolePermissionTemplateGallery
                :loading="roleLoading || permissionLoading || permissionTemplateLoading"
                :permissions="permissions"
                :roles="roles"
                :templates="permissionTemplates"
              />

              <RolePermissionMatrixPanel
                :loading="roleLoading || permissionLoading"
                :permissions="permissions"
                :roles="roles"
              />
            </div>

            <a-table
              :columns="roleColumns"
              :data-source="filteredRoles"
              :loading="roleLoading"
              row-key="id"
              :pagination="{ pageSize: 8, showSizeChanger: false }"
            >
              <template #emptyText>
                <a-empty description="暂无角色数据" />
              </template>

              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'data_scope'">
                  <a-tag color="geekblue">
                    {{ dataScopeLabelMap[record.data_scope] || record.data_scope }}
                  </a-tag>
                </template>

                <template v-else-if="column.key === 'permissions'">
                  <div class="permission-cell">
                    <strong>{{ record.permissions.length }}</strong>
                    <span>已配置权限项</span>
                  </div>
                </template>

                <template v-else-if="column.key === 'status'">
                  <a-tag :color="record.status ? 'green' : 'default'">
                    {{ record.status ? "启用" : "停用" }}
                  </a-tag>
                </template>

                <template v-else-if="column.key === 'updated_at'">
                  {{ formatDateTime(record.updated_at) }}
                </template>

                <template v-else-if="column.key === 'actions'">
                  <a-button v-if="canManageRoles" type="link" @click="openEditRole(record)">编辑</a-button>
                </template>
              </template>
            </a-table>
          </a-tab-pane>

          <a-tab-pane v-if="canManagePermissions" key="permissions" tab="权限项管理">
            <div class="tab-toolbar">
              <a-input-search
                v-model:value="permissionKeyword"
                allow-clear
                class="toolbar-search"
                placeholder="按权限编码、名称、模块或上级权限筛选"
              />

              <a-space wrap>
                <a-button :loading="permissionLoading" @click="loadPermissionsData">刷新权限</a-button>
                <a-button v-if="canManagePermissions" type="primary" @click="openCreatePermission">新建权限</a-button>
              </a-space>
            </div>

            <a-table
              :columns="permissionColumns"
              :data-source="filteredPermissions"
              :loading="permissionLoading"
              row-key="id"
              :pagination="{ pageSize: 8, showSizeChanger: false }"
            >
              <template #emptyText>
                <a-empty description="暂无权限项数据" />
              </template>

              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'permission_name'">
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

                <template v-else-if="column.key === 'parent_name'">
                  {{ record.parent_name || "顶级权限" }}
                </template>

                <template v-else-if="column.key === 'route_path'">
                  <span class="route-text">{{ record.route_path || "-" }}</span>
                </template>

                <template v-else-if="column.key === 'status'">
                  <a-tag :color="record.status ? 'green' : 'default'">
                    {{ record.status ? "启用" : "停用" }}
                  </a-tag>
                </template>

                <template v-else-if="column.key === 'updated_at'">
                  {{ formatDateTime(record.updated_at) }}
                </template>

                <template v-else-if="column.key === 'actions'">
                  <a-button v-if="canManagePermissions" type="link" @click="openEditPermission(record)">编辑</a-button>
                </template>
              </template>
            </a-table>
          </a-tab-pane>

          <a-tab-pane v-if="canManageDepartments" key="departments" tab="组织管理">
            <div class="tab-toolbar">
              <a-input-search
                v-model:value="departmentKeyword"
                allow-clear
                class="toolbar-search"
                placeholder="按部门编码、名称或审批负责人筛选"
              />

              <a-space wrap>
                <a-button :loading="departmentLoading" @click="loadDepartmentsData">刷新部门</a-button>
                <a-button v-if="canManageDepartments" type="primary" @click="openCreateDepartment">新建部门</a-button>
              </a-space>
            </div>

            <a-table
              :columns="departmentColumns"
              :data-source="filteredDepartments"
              :loading="departmentLoading"
              row-key="id"
              :pagination="{ pageSize: 10, showSizeChanger: false }"
            >
              <template #emptyText>
                <a-empty description="暂无部门数据" />
              </template>

              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'dept_name'">
                  <div
                    class="department-cell"
                    :style="{ paddingLeft: `${Math.max(record.dept_level - 1, 0) * 18}px` }"
                  >
                    <strong>{{ record.dept_name }}</strong>
                    <span>{{ record.dept_code }}</span>
                  </div>
                </template>

                <template v-else-if="column.key === 'approver_user_name'">
                  {{ record.approver_user_name || "未指定" }}
                </template>

                <template v-else-if="column.key === 'status'">
                  <a-tag :color="record.status ? 'green' : 'default'">
                    {{ record.status ? "启用" : "停用" }}
                  </a-tag>
                </template>

                <template v-else-if="column.key === 'updated_at'">
                  {{ formatDateTime(record.updated_at) }}
                </template>

                <template v-else-if="column.key === 'actions'">
                  <a-button v-if="canManageDepartments" type="link" @click="openEditDepartment(record)">编辑</a-button>
                </template>
              </template>
            </a-table>
          </a-tab-pane>

          <a-tab-pane v-if="canAccessSystemManagement" key="health" tab="系统健康">
            <a-spin :spinning="healthLoading">
              <div class="health-grid">
                <a-card :bordered="false" class="health-card">
                  <span>服务名称</span>
                  <strong>{{ healthPayload?.service || "-" }}</strong>
                </a-card>
                <a-card :bordered="false" class="health-card">
                  <span>当前状态</span>
                  <strong>{{ healthStatusLabel }}</strong>
                </a-card>
                <a-card :bordered="false" class="health-card">
                  <span>版本号</span>
                  <strong>{{ healthPayload?.version || "-" }}</strong>
                </a-card>
                <a-card :bordered="false" class="health-card">
                  <span>最近时间</span>
                  <strong>{{ formatDateTime(healthPayload?.time || null) }}</strong>
                </a-card>
              </div>
            </a-spin>

            <a-card :bordered="false" class="health-detail-card">
              <template #title>后端健康详情</template>

              <a-descriptions bordered :column="2" size="small">
                <a-descriptions-item label="服务名称">
                  {{ healthPayload?.service || "-" }}
                </a-descriptions-item>
                <a-descriptions-item label="状态">
                  <a-tag :color="healthPayload?.status === 'ok' ? 'green' : 'red'">
                    {{ healthStatusLabel }}
                  </a-tag>
                </a-descriptions-item>
                <a-descriptions-item label="时间">
                  {{ formatDateTime(healthPayload?.time || null) }}
                </a-descriptions-item>
                <a-descriptions-item label="版本">
                  {{ healthPayload?.version || "-" }}
                </a-descriptions-item>
              </a-descriptions>

              <a-alert
                class="health-alert"
                type="success"
                show-icon
                message="当前健康检查接口为匿名只读接口，适合联调和启动自检，不承载业务敏感信息。"
              />
            </a-card>
          </a-tab-pane>
        </a-tabs>
      </a-card>
    </template>

    <a-result
      v-else
      status="403"
      title="当前账号无权访问系统管理"
      sub-title="请联系管理员分配系统配置权限，或返回工作台处理业务模块。"
    >
      <template #extra>
        <RouterLink to="/">
          <a-button type="primary">返回工作台</a-button>
        </RouterLink>
      </template>
    </a-result>

    <a-modal
      v-model:open="userModalOpen"
      :confirm-loading="userSubmitting"
      :title="editingUserId ? '编辑用户' : '新建用户'"
      width="820px"
      @ok="handleSubmitUser"
    >
      <a-form layout="vertical">
        <div class="form-grid">
          <a-form-item label="所属部门" required>
            <a-select
              v-model:value="userForm.dept_id"
              allow-clear
              :options="departmentSelectOptions"
              placeholder="请选择所属部门"
              show-search
              option-filter-prop="label"
            />
          </a-form-item>

          <a-form-item label="登录账号" required>
            <a-input v-model:value="userForm.username" maxlength="64" placeholder="请输入登录账号" />
          </a-form-item>

          <a-form-item :label="editingUserId ? '重置密码' : '登录密码'" required>
            <a-input-password
              v-model:value="userForm.password"
              :placeholder="editingUserId ? '如需重置密码请填写，不改则留空' : '请输入登录密码'"
            />
          </a-form-item>

          <a-form-item label="真实姓名" required>
            <a-input v-model:value="userForm.real_name" maxlength="100" placeholder="请输入真实姓名" />
          </a-form-item>

          <a-form-item label="邮箱">
            <a-input v-model:value="userForm.email" maxlength="100" placeholder="可选，填写通知邮箱" />
          </a-form-item>

          <a-form-item label="手机号">
            <a-input v-model:value="userForm.phone" maxlength="32" placeholder="可选，填写手机号" />
          </a-form-item>

          <a-form-item label="最高密级" required>
            <a-select
              v-model:value="userForm.security_clearance_level"
              :options="securityOptions"
              placeholder="请选择最高密级"
            />
          </a-form-item>

          <a-form-item label="角色配置">
            <a-select
              v-model:value="userForm.role_ids"
              mode="multiple"
              :max-tag-count="'responsive'"
              :options="roleSelectOptions"
              placeholder="可为当前用户配置多个角色"
              show-search
              option-filter-prop="label"
            />
          </a-form-item>

          <a-form-item label="是否启用">
            <a-switch
              v-model:checked="userForm.status"
              checked-children="启用"
              un-checked-children="停用"
            />
          </a-form-item>

          <a-form-item label="是否后台人员">
            <a-switch
              v-model:checked="userForm.is_staff"
              checked-children="是"
              un-checked-children="否"
            />
          </a-form-item>
        </div>

        <a-form-item label="备注">
          <a-textarea
            v-model:value="userForm.remark"
            :rows="3"
            maxlength="255"
            placeholder="可补充该用户的岗位说明、权限边界或使用备注"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="roleModalOpen"
      :confirm-loading="roleSubmitting"
      :title="editingRoleId ? '编辑角色' : '新建角色'"
      width="860px"
      @ok="handleSubmitRole"
    >
      <a-form layout="vertical">
        <div class="form-grid">
          <a-form-item label="角色编码" required>
            <a-input v-model:value="roleForm.role_code" maxlength="64" placeholder="如 ADMIN、ARCHIVIST" />
          </a-form-item>

          <a-form-item label="角色名称" required>
            <a-input v-model:value="roleForm.role_name" maxlength="100" placeholder="请输入角色名称" />
          </a-form-item>

          <a-form-item label="数据范围" required>
            <a-select
              v-model:value="roleForm.data_scope"
              :options="dataScopeOptions"
              placeholder="请选择数据范围"
            />
          </a-form-item>

          <a-form-item label="状态">
            <a-switch
              v-model:checked="roleForm.status"
              checked-children="启用"
              un-checked-children="停用"
            />
          </a-form-item>
        </div>

        <a-form-item label="快捷授权">
          <div class="template-toolbar">
            <a-select
              v-model:value="selectedRoleTemplateKey"
              allow-clear
              class="template-select"
              :loading="permissionTemplateLoading"
              :options="permissionTemplateOptions"
              placeholder="选择系统默认权限模板"
            />

            <a-space wrap>
              <a-button :disabled="!selectedRoleTemplate" @click="handleApplyRoleTemplate('replace')">
                套用模板
              </a-button>
              <a-button :disabled="!selectedRoleTemplate" @click="handleApplyRoleTemplate('append')">
                叠加模板
              </a-button>
              <a-button @click="handleSelectAllPermissions">全选权限</a-button>
              <a-button @click="handleClearRolePermissions">清空权限</a-button>
            </a-space>
          </div>

          <div v-if="selectedRoleTemplate" class="template-hint">
            <strong>{{ selectedRoleTemplate.template_name }}</strong>
            <span>{{ selectedRoleTemplate.description }}</span>
            <small>当前模板可匹配 {{ selectedRoleTemplateResolvedCount }} 项启用权限。</small>
          </div>
        </a-form-item>

        <a-form-item label="模块快捷选择">
          <div class="permission-group-grid">
            <button
              v-for="group in permissionModuleGroups"
              :key="group.module_name"
              class="permission-group-card"
              :class="{ 'permission-group-card-active': isPermissionGroupFullySelected(group.permission_ids) }"
              type="button"
              @click="togglePermissionGroup(group.permission_ids)"
            >
              <strong>{{ group.module_label }}</strong>
              <span>已选 {{ countSelectedPermissions(group.permission_ids) }}/{{ group.permission_ids.length }}</span>
              <small>{{ group.permission_count }} 项启用权限</small>
            </button>
          </div>
        </a-form-item>

        <a-form-item label="权限配置">
          <div class="permission-summary">
            <span>已选权限 {{ roleForm.permission_ids.length }} 项</span>
            <small>可继续通过模板、模块快捷选择或下方明细多选进行调整。</small>
          </div>
          <a-select
            v-model:value="roleForm.permission_ids"
            mode="multiple"
            :max-tag-count="'responsive'"
            :options="permissionSelectOptions"
            placeholder="按模块选择角色可用权限"
            show-search
            option-filter-prop="label"
          />
        </a-form-item>

        <a-form-item label="备注">
          <a-textarea
            v-model:value="roleForm.remark"
            :rows="3"
            maxlength="255"
            placeholder="可说明角色适用部门、授权边界和职责说明"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="departmentModalOpen"
      :confirm-loading="departmentSubmitting"
      :title="editingDepartmentId ? '编辑部门' : '新建部门'"
      width="820px"
      @ok="handleSubmitDepartment"
    >
      <a-form layout="vertical">
        <div class="form-grid">
          <a-form-item label="上级部门">
            <a-select
              v-model:value="departmentForm.parent_id"
              allow-clear
              :options="departmentParentOptions"
              placeholder="顶级部门可留空"
              show-search
              option-filter-prop="label"
            />
          </a-form-item>

          <a-form-item label="部门编码" required>
            <a-input v-model:value="departmentForm.dept_code" maxlength="64" placeholder="请输入部门编码" />
          </a-form-item>

          <a-form-item label="部门名称" required>
            <a-input v-model:value="departmentForm.dept_name" maxlength="100" placeholder="请输入部门名称" />
          </a-form-item>

          <a-form-item label="排序值">
            <a-input-number
              v-model:value="departmentForm.sort_order"
              :min="0"
              class="number-input"
              placeholder="数值越小越靠前"
            />
          </a-form-item>

          <a-form-item label="审批负责人">
            <a-select
              v-model:value="departmentForm.approver_user_id"
              allow-clear
              :options="approverSelectOptions"
              placeholder="可指定部门审批负责人"
              show-search
              option-filter-prop="label"
            />
          </a-form-item>

          <a-form-item label="状态">
            <a-switch
              v-model:checked="departmentForm.status"
              checked-children="启用"
              un-checked-children="停用"
            />
          </a-form-item>
        </div>

        <a-form-item label="备注">
          <a-textarea
            v-model:value="departmentForm.remark"
            :rows="3"
            maxlength="255"
            placeholder="可填写组织职责说明、归档范围或审批说明"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal
      v-model:open="permissionModalOpen"
      :confirm-loading="permissionSubmitting"
      :title="editingPermissionId ? '编辑权限项' : '新建权限项'"
      width="820px"
      @ok="handleSubmitPermission"
    >
      <a-form layout="vertical">
        <div class="form-grid">
          <a-form-item label="上级权限">
            <a-select
              v-model:value="permissionForm.parent_id"
              allow-clear
              :options="permissionParentOptions"
              placeholder="顶级权限可留空"
              show-search
              option-filter-prop="label"
            />
          </a-form-item>

          <a-form-item label="权限编码" required>
            <a-input
              v-model:value="permissionForm.permission_code"
              maxlength="100"
              placeholder="例如 archive_preview_apply"
            />
          </a-form-item>

          <a-form-item label="权限名称" required>
            <a-input
              v-model:value="permissionForm.permission_name"
              maxlength="100"
              placeholder="请输入权限名称"
            />
          </a-form-item>

          <a-form-item label="权限类型" required>
            <a-select
              v-model:value="permissionForm.permission_type"
              :options="permissionTypeOptions"
              placeholder="请选择权限类型"
            />
          </a-form-item>

          <a-form-item label="所属模块" required>
            <a-input
              v-model:value="permissionForm.module_name"
              maxlength="64"
              placeholder="例如 archives、borrowing"
            />
          </a-form-item>

          <a-form-item label="排序值">
            <a-input-number
              v-model:value="permissionForm.sort_order"
              :min="0"
              class="number-input"
              placeholder="数值越小越靠前"
            />
          </a-form-item>

          <a-form-item label="路由或接口地址" class="form-span-2">
            <a-input
              v-model:value="permissionForm.route_path"
              maxlength="255"
              placeholder="可填写前端路由或后端接口路径"
            />
          </a-form-item>

          <a-form-item label="状态">
            <a-switch
              v-model:checked="permissionForm.status"
              checked-children="启用"
              un-checked-children="停用"
            />
          </a-form-item>
        </div>
      </a-form>
    </a-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from "vue"
import { message } from "ant-design-vue"
import { RouterLink, useRoute, useRouter } from "vue-router"

import RolePermissionMatrixPanel from "@/views/system/components/RolePermissionMatrixPanel.vue"
import RolePermissionTemplateGallery from "@/views/system/components/RolePermissionTemplateGallery.vue"
import {
  createPermission,
  createRole,
  createUser,
  fetchPermissions,
  fetchPermissionTemplates,
  fetchRoles,
  fetchUsers,
  unlockUser,
  updatePermission,
  updateRole,
  updateUser,
  type PermissionTemplateItem,
  type RoleItem,
  type RolePayload,
  type SystemPermissionItem,
  type SystemPermissionPayload,
  type UserItem,
  type UserPayload,
} from "@/api/accounts"
import {
  createDepartment,
  fetchDepartments,
  updateDepartment,
  type DepartmentOption,
  type DepartmentPayload,
} from "@/api/organizations"
import { fetchSystemHealth, type SystemHealthPayload } from "@/api/system"
import { useAuthStore } from "@/stores/auth"
import { profileHasAnyPermission } from "@/utils/access"

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()
const USER_TABLE_PAGE_SIZE = 8

const securityLabelMap: Record<string, string> = {
  PUBLIC: "公开",
  INTERNAL: "内部",
  SECRET: "秘密",
  CONFIDENTIAL: "机密",
  TOP_SECRET: "绝密",
}

const dataScopeLabelMap: Record<string, string> = {
  SELF: "仅本人",
  DEPT: "本部门",
  DEPT_AND_CHILD: "本部门及子部门",
  ALL: "全部",
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

const activeTab = ref("users")
const userKeyword = ref("")
const roleKeyword = ref("")
const permissionKeyword = ref("")
const departmentKeyword = ref("")
const focusedUserId = ref<number | null>(null)

const userLoading = ref(false)
const roleLoading = ref(false)
const permissionLoading = ref(false)
const permissionTemplateLoading = ref(false)
const departmentLoading = ref(false)
const healthLoading = ref(false)

const userSubmitting = ref(false)
const roleSubmitting = ref(false)
const permissionSubmitting = ref(false)
const departmentSubmitting = ref(false)
const unlockingUserId = ref<number | null>(null)

const userModalOpen = ref(false)
const roleModalOpen = ref(false)
const permissionModalOpen = ref(false)
const departmentModalOpen = ref(false)

const editingUserId = ref<number | null>(null)
const editingRoleId = ref<number | null>(null)
const editingPermissionId = ref<number | null>(null)
const editingDepartmentId = ref<number | null>(null)

const users = ref<UserItem[]>([])
const roles = ref<RoleItem[]>([])
const permissions = ref<SystemPermissionItem[]>([])
const permissionTemplates = ref<PermissionTemplateItem[]>([])
const departments = ref<DepartmentOption[]>([])
const healthPayload = ref<SystemHealthPayload | null>(null)
const selectedRoleTemplateKey = ref<string | undefined>(undefined)
const userPagination = reactive({
  current: 1,
  pageSize: USER_TABLE_PAGE_SIZE,
})

const userForm = reactive({
  dept_id: undefined as number | undefined,
  username: "",
  password: "",
  real_name: "",
  email: "",
  phone: "",
  security_clearance_level: "INTERNAL",
  status: true,
  is_staff: true,
  role_ids: [] as number[],
  remark: "",
})

const roleForm = reactive({
  role_code: "",
  role_name: "",
  data_scope: "SELF",
  status: true,
  permission_ids: [] as number[],
  remark: "",
})

const permissionForm = reactive({
  parent_id: undefined as number | undefined,
  permission_code: "",
  permission_name: "",
  permission_type: "MENU",
  module_name: "",
  route_path: "",
  sort_order: 0,
  status: true,
})

const departmentForm = reactive({
  parent_id: undefined as number | undefined,
  dept_code: "",
  dept_name: "",
  sort_order: 0,
  approver_user_id: undefined as number | undefined,
  status: true,
  remark: "",
})

const securityOptions = Object.entries(securityLabelMap).map(([value, label]) => ({ value, label }))
const dataScopeOptions = Object.entries(dataScopeLabelMap).map(([value, label]) => ({ value, label }))
const permissionTypeOptions = Object.entries(permissionTypeLabelMap).map(([value, label]) => ({ value, label }))

const userColumns = [
  { title: "用户", key: "user" },
  { title: "所属部门", key: "dept_name", dataIndex: "dept_name", width: 160 },
  { title: "角色", key: "roles", width: 220 },
  { title: "密级", key: "security_clearance_level", width: 120 },
  { title: "状态", key: "status", width: 100 },
  { title: "锁定情况", key: "lock_state", width: 220 },
  { title: "最近登录", key: "last_login_at", width: 180 },
  { title: "操作", key: "actions", width: 150 },
]

const roleColumns = [
  { title: "角色编码", key: "role_code", dataIndex: "role_code", width: 180 },
  { title: "角色名称", key: "role_name", dataIndex: "role_name", width: 160 },
  { title: "数据范围", key: "data_scope", width: 160 },
  { title: "权限数量", key: "permissions", width: 150 },
  { title: "状态", key: "status", width: 100 },
  { title: "最近更新", key: "updated_at", width: 180 },
  { title: "操作", key: "actions", width: 120 },
]

const permissionColumns = [
  { title: "权限", key: "permission_name" },
  { title: "类型", key: "permission_type", width: 110 },
  { title: "模块", key: "module_name", dataIndex: "module_name", width: 140 },
  { title: "上级权限", key: "parent_name", width: 160 },
  { title: "路由/接口", key: "route_path", width: 220 },
  { title: "排序值", key: "sort_order", dataIndex: "sort_order", width: 100 },
  { title: "状态", key: "status", width: 100 },
  { title: "最近更新", key: "updated_at", width: 180 },
  { title: "操作", key: "actions", width: 120 },
]

const departmentColumns = [
  { title: "部门", key: "dept_name" },
  { title: "上级部门", key: "parent_name", dataIndex: "parent_name", width: 160 },
  { title: "层级", key: "dept_level", dataIndex: "dept_level", width: 90 },
  { title: "审批负责人", key: "approver_user_name", width: 160 },
  { title: "排序值", key: "sort_order", dataIndex: "sort_order", width: 100 },
  { title: "状态", key: "status", width: 100 },
  { title: "最近更新", key: "updated_at", width: 180 },
  { title: "操作", key: "actions", width: 120 },
]

const canAccessSystemManagement = computed(() =>
  profileHasAnyPermission(
    authStore.profile,
    [
      "menu.system_management",
      "button.system.user.manage",
      "button.system.role.manage",
      "button.system.permission.manage",
      "button.system.department.manage",
    ],
    ["ADMIN"],
  ),
)

const canManageUsers = computed(() =>
  profileHasAnyPermission(authStore.profile, ["button.system.user.manage"], ["ADMIN"]),
)

const canManageRoles = computed(() =>
  profileHasAnyPermission(authStore.profile, ["button.system.role.manage"], ["ADMIN"]),
)

const canManagePermissions = computed(() =>
  profileHasAnyPermission(authStore.profile, ["button.system.permission.manage"], ["ADMIN"]),
)

const canManageDepartments = computed(() =>
  profileHasAnyPermission(authStore.profile, ["button.system.department.manage"], ["ADMIN"]),
)

const canLoadRoleOptions = computed(() => canManageUsers.value || canManageRoles.value)
const canLoadPermissionCatalog = computed(() => canManagePermissions.value || canManageRoles.value)
const canLoadDepartmentOptions = computed(() => canManageUsers.value || canManageDepartments.value)
const visibleTabKeys = computed(() => {
  const tabKeys: string[] = []

  if (canManageUsers.value) {
    tabKeys.push("users")
  }
  if (canManageRoles.value) {
    tabKeys.push("roles")
  }
  if (canManagePermissions.value) {
    tabKeys.push("permissions")
  }
  if (canManageDepartments.value) {
    tabKeys.push("departments")
  }
  if (canAccessSystemManagement.value) {
    tabKeys.push("health")
  }

  return tabKeys
})

const filteredUsers = computed(() => {
  const keyword = userKeyword.value.trim().toLowerCase()
  if (!keyword) {
    return users.value
  }
  return users.value.filter((item) =>
    [item.username, item.real_name, item.email, item.dept_name]
      .filter(Boolean)
      .some((field) => String(field).toLowerCase().includes(keyword)),
  )
})

const filteredRoles = computed(() => {
  const keyword = roleKeyword.value.trim().toLowerCase()
  if (!keyword) {
    return roles.value
  }
  return roles.value.filter((item) =>
    [item.role_code, item.role_name, dataScopeLabelMap[item.data_scope] || item.data_scope]
      .some((field) => String(field).toLowerCase().includes(keyword)),
  )
})

const filteredPermissions = computed(() => {
  const keyword = permissionKeyword.value.trim().toLowerCase()
  if (!keyword) {
    return permissions.value
  }
  return permissions.value.filter((item) =>
    [
      item.permission_code,
      item.permission_name,
      item.module_name,
      item.parent_name,
      permissionTypeLabelMap[item.permission_type] || item.permission_type,
    ]
      .filter(Boolean)
      .some((field) => String(field).toLowerCase().includes(keyword)),
  )
})

const filteredDepartments = computed(() => {
  const keyword = departmentKeyword.value.trim().toLowerCase()
  if (!keyword) {
    return departments.value
  }
  return departments.value.filter((item) =>
    [item.dept_code, item.dept_name, item.approver_user_name, item.parent_name]
      .filter(Boolean)
      .some((field) => String(field).toLowerCase().includes(keyword)),
  )
})

const summaryCards = computed(() => {
  const cards: Array<{ label: string; value: number | string; caption: string }> = []

  if (canManageUsers.value) {
    cards.push(
      {
        label: "用户总数",
        value: users.value.length,
        caption: `${users.value.filter((item) => item.status).length} 个启用账号`,
      },
      {
        label: "锁定账号",
        value: users.value.filter((item) => Boolean(item.lock_until_at)).length,
        caption: "连续输错密码后进入锁定期的账号数量",
      },
    )
  }

  if (canManageRoles.value && canManagePermissions.value) {
    cards.push({
      label: "授权资源",
      value: roles.value.filter((item) => item.status).length,
      caption: `${permissions.value.filter((item) => item.status).length} 个启用权限项`,
    })
  } else if (canManageRoles.value) {
    cards.push({
      label: "有效角色",
      value: roles.value.filter((item) => item.status).length,
      caption: `${permissions.value.filter((item) => item.status).length} 个可分配权限项`,
    })
  } else if (canManagePermissions.value) {
    cards.push({
      label: "权限项总数",
      value: permissions.value.filter((item) => item.status).length,
      caption: "当前可维护的启用权限项总数",
    })
  }

  if (canManageDepartments.value) {
    cards.push({
      label: "启用部门",
      value: departments.value.filter((item) => item.status).length,
      caption: "包含已配置审批负责人的组织节点",
    })
  }

  cards.push({
    label: "后端状态",
    value: healthStatusLabel.value,
    caption: healthPayload.value?.time ? `最近检查 ${formatDateTime(healthPayload.value.time)}` : "尚未执行健康检查",
  })

  return cards
})

const healthStatusLabel = computed(() => {
  if (!healthPayload.value?.status) {
    return "待检查"
  }
  return healthPayload.value.status === "ok" ? "运行正常" : "状态异常"
})

const roleSelectOptions = computed(() =>
  roles.value
    .filter((item) => item.status)
    .map((item) => ({
      value: item.id,
      label: `${item.role_name}（${item.role_code}）`,
    })),
)

const permissionSelectOptions = computed(() =>
  permissions.value
    .filter((item) => item.status)
    .map((item) => ({
      value: item.id,
      label: `${item.module_name} / ${item.permission_name}（${item.permission_code}）`,
    })),
)

const permissionCodeToIdMap = computed(
  () => new Map(permissions.value.filter((item) => item.status).map((item) => [item.permission_code, item.id])),
)

const permissionTemplateOptions = computed(() =>
  permissionTemplates.value.map((item) => ({
    value: item.template_key,
    label: `${item.template_name}（${item.permission_codes.length} 项）`,
  })),
)

const selectedRoleTemplate = computed(
  () => permissionTemplates.value.find((item) => item.template_key === selectedRoleTemplateKey.value) || null,
)

const selectedRoleTemplateResolvedCount = computed(() => resolveTemplatePermissionIds(selectedRoleTemplate.value).length)

const permissionModuleGroups = computed(() => {
  const groupMap = new Map<
    string,
    {
      module_name: string
      module_label: string
      permission_ids: number[]
      permission_count: number
    }
  >()

  permissions.value
    .filter((item) => item.status)
    .sort((left, right) => left.sort_order - right.sort_order || left.id - right.id)
    .forEach((item) => {
      const existingGroup = groupMap.get(item.module_name)
      if (existingGroup) {
        existingGroup.permission_ids.push(item.id)
        existingGroup.permission_count += 1
        return
      }
      groupMap.set(item.module_name, {
        module_name: item.module_name,
        module_label: permissionModuleLabelMap[item.module_name] || item.module_name,
        permission_ids: [item.id],
        permission_count: 1,
      })
    })

  return [...groupMap.values()]
})

const permissionParentOptions = computed(() =>
  permissions.value
    .filter((item) => item.id !== editingPermissionId.value)
    .map((item) => ({
      value: item.id,
      label: `${item.permission_name}（${item.permission_code}）`,
    })),
)

const departmentSelectOptions = computed(() =>
  departments.value
    .filter((item) => item.status)
    .map((item) => ({
      value: item.id,
      label: `${"　".repeat(Math.max(item.dept_level - 1, 0))}${item.dept_name}（${item.dept_code}）`,
    })),
)

const approverSelectOptions = computed(() =>
  users.value
    .filter((item) => item.status)
    .map((item) => ({
      value: item.id,
      label: `${item.real_name}（${item.username} / ${item.dept_name}）`,
    })),
)

const departmentParentOptions = computed(() => {
  const currentDepartment = departments.value.find((item) => item.id === editingDepartmentId.value)
  return departments.value
    .filter((item) => {
      if (!currentDepartment) {
        return true
      }
      if (item.id === currentDepartment.id) {
        return false
      }
      return !item.dept_path.startsWith(`${currentDepartment.dept_path}/`)
    })
    .map((item) => ({
      value: item.id,
      label: `${"　".repeat(Math.max(item.dept_level - 1, 0))}${item.dept_name}（${item.dept_code}）`,
    }))
})

function resetUserForm() {
  userForm.dept_id = undefined
  userForm.username = ""
  userForm.password = ""
  userForm.real_name = ""
  userForm.email = ""
  userForm.phone = ""
  userForm.security_clearance_level = "INTERNAL"
  userForm.status = true
  userForm.is_staff = true
  userForm.role_ids = []
  userForm.remark = ""
}

function resetRoleForm() {
  roleForm.role_code = ""
  roleForm.role_name = ""
  roleForm.data_scope = "SELF"
  roleForm.status = true
  roleForm.permission_ids = []
  roleForm.remark = ""
  selectedRoleTemplateKey.value = undefined
}

function resetPermissionForm() {
  permissionForm.parent_id = undefined
  permissionForm.permission_code = ""
  permissionForm.permission_name = ""
  permissionForm.permission_type = "MENU"
  permissionForm.module_name = ""
  permissionForm.route_path = ""
  permissionForm.sort_order = 0
  permissionForm.status = true
}

function resetDepartmentForm() {
  departmentForm.parent_id = undefined
  departmentForm.dept_code = ""
  departmentForm.dept_name = ""
  departmentForm.sort_order = 0
  departmentForm.approver_user_id = undefined
  departmentForm.status = true
  departmentForm.remark = ""
}

function normalizeOptionalText(value: string) {
  const trimmed = value.trim()
  return trimmed || null
}

function formatDateTime(value: string | null) {
  if (!value) {
    return "-"
  }
  return value.replace("T", " ").slice(0, 19)
}

function normalizePermissionIds(permissionIds: number[]) {
  return [...new Set(permissionIds)]
}

function handleUserTableChange(page: number, pageSize: number) {
  userPagination.current = page
  userPagination.pageSize = pageSize
}

function getUserRowClassName(record: UserItem) {
  return record.id === focusedUserId.value ? "user-row-focused" : ""
}

function resolveRouteTab() {
  const rawTab = Array.isArray(route.query.tab) ? route.query.tab[0] : route.query.tab
  if (typeof rawTab !== "string") {
    return null
  }
  const normalizedTab = rawTab.trim()
  return normalizedTab || null
}

function resolveRouteUserId() {
  const rawUserId = Array.isArray(route.query.userId) ? route.query.userId[0] : route.query.userId
  const userId = Number(rawUserId)
  if (!Number.isInteger(userId) || userId <= 0) {
    return null
  }
  return userId
}

async function clearManagementRouteTarget() {
  if (!route.query.tab && !route.query.userId) {
    return
  }
  const nextQuery = { ...route.query }
  delete nextQuery.tab
  delete nextQuery.userId
  await router.replace({ query: nextQuery })
}

async function scrollToFocusedUser() {
  await nextTick()
  window.setTimeout(() => {
    const row = document.querySelector<HTMLElement>(`.ant-table-row[data-row-key="${focusedUserId.value}"]`)
    row?.scrollIntoView({ behavior: "smooth", block: "center" })
  }, 80)
}

function resolveUserPage(userId: number) {
  const targetIndex = filteredUsers.value.findIndex((item) => item.id === userId)
  if (targetIndex < 0) {
    return 1
  }
  return Math.floor(targetIndex / userPagination.pageSize) + 1
}

async function consumeManagementRouteTarget() {
  const routeUserId = resolveRouteUserId()
  if (routeUserId && canManageUsers.value && visibleTabKeys.value.includes("users")) {
    if (!users.value.length && !userLoading.value) {
      await loadUsersData()
    }

    userKeyword.value = ""
    activeTab.value = "users"

    const targetUser = users.value.find((item) => item.id === routeUserId)
    if (!targetUser) {
      focusedUserId.value = null
      await clearManagementRouteTarget()
      message.warning("目标用户不存在或已被删除。")
      return
    }

    userPagination.current = resolveUserPage(routeUserId)
    focusedUserId.value = routeUserId
    await scrollToFocusedUser()
    openEditUser(targetUser)
    await clearManagementRouteTarget()
    return
  }

  const routeTab = resolveRouteTab()
  if (routeTab && visibleTabKeys.value.includes(routeTab)) {
    activeTab.value = routeTab
    await clearManagementRouteTarget()
    return
  }

  if (route.query.tab || route.query.userId) {
    if (visibleTabKeys.value.length) {
      activeTab.value = visibleTabKeys.value[0]
    }
    await clearManagementRouteTarget()
  }
}

function resolveTemplatePermissionIds(template: PermissionTemplateItem | null) {
  if (!template) {
    return []
  }

  return normalizePermissionIds(
    template.permission_codes
      .map((permissionCode) => permissionCodeToIdMap.value.get(permissionCode))
      .filter((permissionId): permissionId is number => Boolean(permissionId)),
  )
}

function syncSelectedRoleTemplate(roleCode?: string | null) {
  if (!roleCode) {
    selectedRoleTemplateKey.value = undefined
    return
  }

  const matchedTemplate = permissionTemplates.value.find((item) => item.role_code === roleCode)
  selectedRoleTemplateKey.value = matchedTemplate?.template_key
}

function handleApplyRoleTemplate(mode: "replace" | "append") {
  if (!selectedRoleTemplate.value) {
    message.warning("请先选择需要套用的权限模板。")
    return
  }

  const resolvedPermissionIds = resolveTemplatePermissionIds(selectedRoleTemplate.value)
  if (!resolvedPermissionIds.length) {
    message.warning("当前模板未匹配到可用权限，请先检查权限初始化是否完成。")
    return
  }

  roleForm.permission_ids = mode === "replace"
    ? resolvedPermissionIds
    : normalizePermissionIds([...roleForm.permission_ids, ...resolvedPermissionIds])
}

function handleSelectAllPermissions() {
  roleForm.permission_ids = permissions.value.filter((item) => item.status).map((item) => item.id)
}

function handleClearRolePermissions() {
  roleForm.permission_ids = []
}

function countSelectedPermissions(permissionIds: number[]) {
  const selectedPermissionIdSet = new Set(roleForm.permission_ids)
  return permissionIds.filter((permissionId) => selectedPermissionIdSet.has(permissionId)).length
}

function isPermissionGroupFullySelected(permissionIds: number[]) {
  return permissionIds.length > 0 && countSelectedPermissions(permissionIds) === permissionIds.length
}

function togglePermissionGroup(permissionIds: number[]) {
  if (isPermissionGroupFullySelected(permissionIds)) {
    roleForm.permission_ids = roleForm.permission_ids.filter((permissionId) => !permissionIds.includes(permissionId))
    return
  }

  roleForm.permission_ids = normalizePermissionIds([...roleForm.permission_ids, ...permissionIds])
}

function openCreateUser() {
  if (!canManageUsers.value) {
    message.error("当前账号无权维护用户。")
    return
  }
  editingUserId.value = null
  resetUserForm()
  userModalOpen.value = true
}

function openEditUser(record: UserItem) {
  if (!canManageUsers.value) {
    message.error("当前账号无权维护用户。")
    return
  }
  editingUserId.value = record.id
  userForm.dept_id = record.dept_id
  userForm.username = record.username
  userForm.password = ""
  userForm.real_name = record.real_name
  userForm.email = record.email || ""
  userForm.phone = record.phone || ""
  userForm.security_clearance_level = record.security_clearance_level
  userForm.status = record.status
  userForm.is_staff = record.is_staff
  userForm.role_ids = record.roles.map((role) => role.id)
  userForm.remark = record.remark || ""
  userModalOpen.value = true
}

function openCreateRole() {
  if (!canManageRoles.value) {
    message.error("当前账号无权维护角色。")
    return
  }
  editingRoleId.value = null
  resetRoleForm()
  roleModalOpen.value = true
}

function openEditRole(record: RoleItem) {
  if (!canManageRoles.value) {
    message.error("当前账号无权维护角色。")
    return
  }
  editingRoleId.value = record.id
  roleForm.role_code = record.role_code
  roleForm.role_name = record.role_name
  roleForm.data_scope = record.data_scope
  roleForm.status = record.status
  roleForm.permission_ids = record.permissions.map((item) => item.id)
  roleForm.remark = record.remark || ""
  syncSelectedRoleTemplate(record.role_code)
  roleModalOpen.value = true
}

function openCreatePermission() {
  if (!canManagePermissions.value) {
    message.error("当前账号无权维护权限项。")
    return
  }
  editingPermissionId.value = null
  resetPermissionForm()
  permissionModalOpen.value = true
}

function openEditPermission(record: SystemPermissionItem) {
  if (!canManagePermissions.value) {
    message.error("当前账号无权维护权限项。")
    return
  }
  editingPermissionId.value = record.id
  permissionForm.parent_id = record.parent_id ?? undefined
  permissionForm.permission_code = record.permission_code
  permissionForm.permission_name = record.permission_name
  permissionForm.permission_type = record.permission_type
  permissionForm.module_name = record.module_name
  permissionForm.route_path = record.route_path || ""
  permissionForm.sort_order = record.sort_order
  permissionForm.status = record.status
  permissionModalOpen.value = true
}

function openCreateDepartment() {
  if (!canManageDepartments.value) {
    message.error("当前账号无权维护组织架构。")
    return
  }
  editingDepartmentId.value = null
  resetDepartmentForm()
  departmentModalOpen.value = true
}

function openEditDepartment(record: DepartmentOption) {
  if (!canManageDepartments.value) {
    message.error("当前账号无权维护组织架构。")
    return
  }
  editingDepartmentId.value = record.id
  departmentForm.parent_id = record.parent_id ?? undefined
  departmentForm.dept_code = record.dept_code
  departmentForm.dept_name = record.dept_name
  departmentForm.sort_order = record.sort_order
  departmentForm.approver_user_id = record.approver_user_id ?? undefined
  departmentForm.status = record.status
  departmentForm.remark = record.remark || ""
  departmentModalOpen.value = true
}

async function loadUsersData() {
  userLoading.value = true
  try {
    const response = await fetchUsers()
    users.value = response.data
    if (focusedUserId.value && !users.value.some((item) => item.id === focusedUserId.value)) {
      focusedUserId.value = null
    }
  } catch (error) {
    handleRequestError(error, "加载用户列表失败。")
  } finally {
    userLoading.value = false
  }
}

async function loadRolesData() {
  roleLoading.value = true
  try {
    const roleResponse = await fetchRoles()
    roles.value = roleResponse.data
  } catch (error) {
    handleRequestError(error, "加载角色数据失败。")
  } finally {
    roleLoading.value = false
  }
}

async function loadPermissionsData() {
  permissionLoading.value = true
  try {
    const response = await fetchPermissions()
    permissions.value = response.data
  } catch (error) {
    handleRequestError(error, "加载权限项数据失败。")
  } finally {
    permissionLoading.value = false
  }
}

async function loadPermissionTemplatesData() {
  permissionTemplateLoading.value = true
  try {
    const response = await fetchPermissionTemplates()
    permissionTemplates.value = response.data
    syncSelectedRoleTemplate(roleForm.role_code)
  } catch (error) {
    handleRequestError(error, "加载权限模板失败。")
  } finally {
    permissionTemplateLoading.value = false
  }
}

async function loadDepartmentsData() {
  departmentLoading.value = true
  try {
    const response = await fetchDepartments()
    departments.value = response.data
  } catch (error) {
    handleRequestError(error, "加载部门列表失败。")
  } finally {
    departmentLoading.value = false
  }
}

async function loadHealthData() {
  healthLoading.value = true
  try {
    const response = await fetchSystemHealth()
    healthPayload.value = response.data
  } catch (error) {
    handleRequestError(error, "加载系统健康状态失败。")
  } finally {
    healthLoading.value = false
  }
}

async function loadPageData() {
  const tasks: Promise<void>[] = [loadHealthData()]

  if (canManageUsers.value) {
    tasks.push(loadUsersData())
  }
  if (canLoadRoleOptions.value) {
    tasks.push(loadRolesData())
  }
  if (canLoadPermissionCatalog.value) {
    tasks.push(loadPermissionsData())
  }
  if (canManageRoles.value) {
    tasks.push(loadPermissionTemplatesData())
  }
  if (canLoadDepartmentOptions.value) {
    tasks.push(loadDepartmentsData())
  }

  await Promise.all(tasks)
}

async function handleSubmitUser() {
  if (!canManageUsers.value) {
    message.error("当前账号无权维护用户。")
    return
  }
  if (!userForm.dept_id) {
    message.error("请选择所属部门。")
    return
  }
  if (!userForm.username.trim()) {
    message.error("请输入登录账号。")
    return
  }
  if (!userForm.real_name.trim()) {
    message.error("请输入真实姓名。")
    return
  }
  if (!editingUserId.value && userForm.password.trim().length < 6) {
    message.error("新建用户时密码长度不能少于 6 位。")
    return
  }

  const payload: UserPayload = {
    dept_id: userForm.dept_id,
    username: userForm.username.trim(),
    real_name: userForm.real_name.trim(),
    email: normalizeOptionalText(userForm.email),
    phone: normalizeOptionalText(userForm.phone),
    security_clearance_level: userForm.security_clearance_level,
    status: userForm.status,
    remark: normalizeOptionalText(userForm.remark),
    is_staff: userForm.is_staff,
    role_ids: [...userForm.role_ids],
  }

  if (userForm.password.trim()) {
    payload.password = userForm.password.trim()
  }

  userSubmitting.value = true
  try {
    const response = editingUserId.value
      ? await updateUser(editingUserId.value, payload)
      : await createUser(payload)
    message.success(response.message)
    userModalOpen.value = false
    await loadUsersData()
  } catch (error) {
    handleRequestError(error, editingUserId.value ? "更新用户失败。" : "创建用户失败。")
  } finally {
    userSubmitting.value = false
  }
}

async function handleSubmitRole() {
  if (!canManageRoles.value) {
    message.error("当前账号无权维护角色。")
    return
  }
  if (!roleForm.role_code.trim()) {
    message.error("请输入角色编码。")
    return
  }
  if (!roleForm.role_name.trim()) {
    message.error("请输入角色名称。")
    return
  }

  const payload: RolePayload = {
    role_code: roleForm.role_code.trim(),
    role_name: roleForm.role_name.trim(),
    data_scope: roleForm.data_scope,
    status: roleForm.status,
    remark: normalizeOptionalText(roleForm.remark),
    permission_ids: [...roleForm.permission_ids],
  }

  roleSubmitting.value = true
  try {
    const response = editingRoleId.value
      ? await updateRole(editingRoleId.value, payload)
      : await createRole(payload)
    message.success(response.message)
    roleModalOpen.value = false
    await loadRolesData()
  } catch (error) {
    handleRequestError(error, editingRoleId.value ? "更新角色失败。" : "创建角色失败。")
  } finally {
    roleSubmitting.value = false
  }
}

async function handleSubmitPermission() {
  if (!canManagePermissions.value) {
    message.error("当前账号无权维护权限项。")
    return
  }
  if (!permissionForm.permission_code.trim()) {
    message.error("请输入权限编码。")
    return
  }
  if (!permissionForm.permission_name.trim()) {
    message.error("请输入权限名称。")
    return
  }
  if (!permissionForm.module_name.trim()) {
    message.error("请输入所属模块。")
    return
  }

  const payload: SystemPermissionPayload = {
    parent_id: permissionForm.parent_id ?? null,
    permission_code: permissionForm.permission_code.trim(),
    permission_name: permissionForm.permission_name.trim(),
    permission_type: permissionForm.permission_type,
    module_name: permissionForm.module_name.trim(),
    route_path: normalizeOptionalText(permissionForm.route_path),
    sort_order: permissionForm.sort_order,
    status: permissionForm.status,
  }

  permissionSubmitting.value = true
  try {
    const response = editingPermissionId.value
      ? await updatePermission(editingPermissionId.value, payload)
      : await createPermission(payload)
    message.success(response.message)
    permissionModalOpen.value = false
    await loadPermissionsData()
  } catch (error) {
    handleRequestError(error, editingPermissionId.value ? "更新权限项失败。" : "创建权限项失败。")
  } finally {
    permissionSubmitting.value = false
  }
}

async function handleSubmitDepartment() {
  if (!canManageDepartments.value) {
    message.error("当前账号无权维护组织架构。")
    return
  }
  if (!departmentForm.dept_code.trim()) {
    message.error("请输入部门编码。")
    return
  }
  if (!departmentForm.dept_name.trim()) {
    message.error("请输入部门名称。")
    return
  }

  const payload: DepartmentPayload = {
    parent_id: departmentForm.parent_id ?? null,
    dept_code: departmentForm.dept_code.trim(),
    dept_name: departmentForm.dept_name.trim(),
    sort_order: departmentForm.sort_order,
    approver_user_id: departmentForm.approver_user_id ?? null,
    status: departmentForm.status,
    remark: normalizeOptionalText(departmentForm.remark),
  }

  departmentSubmitting.value = true
  try {
    const response = editingDepartmentId.value
      ? await updateDepartment(editingDepartmentId.value, payload)
      : await createDepartment(payload)
    message.success(response.message)
    departmentModalOpen.value = false
    await loadDepartmentsData()
  } catch (error) {
    handleRequestError(error, editingDepartmentId.value ? "更新部门失败。" : "创建部门失败。")
  } finally {
    departmentSubmitting.value = false
  }
}

async function handleUnlockUser(userId: number) {
  if (!canManageUsers.value) {
    message.error("当前账号无权解锁账号。")
    return
  }
  unlockingUserId.value = userId
  try {
    const response = await unlockUser(userId)
    message.success(response.message)
    await loadUsersData()
  } catch (error) {
    handleRequestError(error, "解锁账号失败。")
  } finally {
    unlockingUserId.value = null
  }
}

function handleRequestError(error: unknown, fallbackMessage: string) {
  const response = error as { response?: { data?: { message?: string } } }
  if (response?.response?.data?.message) {
    message.error(response.response.data.message)
    return
  }
  message.error(fallbackMessage)
}

onMounted(async () => {
  if (!canAccessSystemManagement.value) {
    return
  }
  await loadPageData()
  await consumeManagementRouteTarget()
})

watch(
  visibleTabKeys,
  (tabKeys) => {
    if (!tabKeys.length) {
      activeTab.value = "health"
      return
    }
    if (!tabKeys.includes(activeTab.value)) {
      activeTab.value = tabKeys[0]
    }
  },
  { immediate: true },
)

watch(
  () => [route.query.tab, route.query.userId],
  ([tab, userId], [oldTab, oldUserId]) => {
    if (!canAccessSystemManagement.value) {
      return
    }
    if ((!tab && !userId) || (tab === oldTab && userId === oldUserId)) {
      return
    }
    void consumeManagementRouteTarget()
  },
)
</script>

<style scoped>
.system-page {
  display: grid;
  gap: 24px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
}

.summary-card,
.health-card {
  border-radius: 22px;
  background:
    radial-gradient(circle at top right, rgba(10, 113, 82, 0.1), transparent 42%),
    rgba(255, 255, 255, 0.96);
}

.summary-card span,
.health-card span {
  display: block;
  color: #667085;
}

.summary-card strong,
.health-card strong {
  display: block;
  margin: 12px 0 8px;
  font-size: 28px;
  line-height: 1.2;
}

.panel-card :deep(.user-row-focused > td) {
  background: rgba(230, 244, 255, 0.88) !important;
}

.panel-card :deep(.user-row-focused:hover > td) {
  background: rgba(186, 224, 255, 0.92) !important;
}

.summary-card small {
  color: #475467;
  line-height: 1.7;
}

.panel-card,
.health-detail-card {
  border-radius: 26px;
}

.page-header,
.tab-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.page-header {
  margin-bottom: 18px;
}

.page-header strong {
  font-size: 18px;
}

.page-header p {
  margin: 8px 0 0;
  color: #475467;
  line-height: 1.7;
}

.tab-toolbar {
  margin-bottom: 18px;
}

.role-insight-stack {
  display: grid;
  gap: 18px;
  margin-bottom: 18px;
}

.toolbar-search {
  max-width: 360px;
}

.user-cell,
.department-cell,
.permission-cell,
.lock-cell {
  display: grid;
  gap: 4px;
}

.user-cell span,
.department-cell span,
.permission-cell span,
.muted-text {
  color: #667085;
  font-size: 12px;
}

.department-cell {
  min-width: 200px;
}

.route-text {
  color: #475467;
  word-break: break-all;
}

.health-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  margin-bottom: 20px;
}

.health-detail-card {
  margin-top: 20px;
}

.health-alert {
  margin-top: 18px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

.form-span-2 {
  grid-column: span 2;
}

.number-input {
  width: 100%;
}

.template-toolbar {
  display: grid;
  gap: 12px;
}

.template-select {
  width: 100%;
}

.template-hint {
  display: grid;
  gap: 6px;
  margin-top: 12px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(10, 113, 82, 0.06);
}

.template-hint span,
.template-hint small,
.permission-summary small {
  color: #667085;
  line-height: 1.7;
}

.permission-group-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.permission-group-card {
  display: grid;
  gap: 6px;
  padding: 16px;
  border: 1px solid rgba(16, 24, 40, 0.08);
  border-radius: 18px;
  background: #ffffff;
  text-align: left;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.permission-group-card:hover {
  transform: translateY(-1px);
  border-color: rgba(10, 113, 82, 0.22);
  box-shadow: 0 12px 24px rgba(15, 23, 42, 0.06);
}

.permission-group-card-active {
  border-color: rgba(10, 113, 82, 0.36);
  background: rgba(10, 113, 82, 0.08);
}

.permission-group-card span,
.permission-group-card small {
  color: #667085;
}

.permission-summary {
  display: grid;
  gap: 4px;
  margin-bottom: 12px;
}

@media (max-width: 960px) {
  .page-header,
  .tab-toolbar {
    flex-direction: column;
  }

  .toolbar-search {
    max-width: none;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .form-span-2 {
    grid-column: span 1;
  }
}
</style>
