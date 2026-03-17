# API 规格说明

说明：本文档基于当前代码中的 Django + DRF 路由、视图、序列化器与测试用例整理，覆盖 `fullstack/backend/config/urls.py` 下的全部对外接口。

## 1. 基础约定

### 1.1 基础地址

- 通过前端反向代理访问：`http://127.0.0.1:8080`
- 直接访问后端：`http://127.0.0.1:8000`
- API 前缀：`/api/v1`

### 1.2 认证方式

- 登录接口返回 JWT：
  - `access`：访问令牌
  - `refresh`：刷新令牌
- 需要认证的接口统一使用请求头：

```http
Authorization: Bearer <access_token>
```

### 1.3 通用响应格式

除文件流与 CSV 下载接口外，统一返回 JSON：

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {}
}
```

说明：

- `code` 与 HTTP 状态码保持一致。
- 失败时仍返回同结构：

```json
{
  "code": 400,
  "message": "参数错误说明",
  "data": null
}
```

### 1.4 分页约定

列表接口默认不分页。满足任一条件时启用分页：

- `paginate=true`
- 传入 `page`
- 传入 `page_size`

分页响应格式：

```json
{
  "code": 200,
  "message": "操作成功",
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 100,
      "total_pages": 5,
      "has_next": true,
      "has_previous": false
    }
  }
}
```

默认分页参数：

- `page`：页码
- `page_size`：每页条数，默认 20，最大 100

### 1.5 权限与访问控制

系统权限模型分为三层：

1. 登录校验
2. 角色兜底校验
3. 精细权限码校验

典型角色：

- `ADMIN`：管理员
- `ARCHIVIST`：档案员
- `BORROWER`：借阅人
- `AUDITOR`：审计员

部分高密级数据会触发字段脱敏，例如档案摘要、责任人、实体位置、文件信息。

## 2. 接口总览

| 模块 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| 根健康 | GET | `/` | 根健康检查 |
| 认证 | POST | `/api/v1/auth/login/` | 登录 |
| 认证 | POST | `/api/v1/auth/logout/` | 退出登录 |
| 认证 | POST | `/api/v1/auth/refresh/` | 刷新访问令牌 |
| 认证 | GET | `/api/v1/auth/profile/` | 获取当前用户资料 |
| 认证 | POST | `/api/v1/auth/unlock/{user_id}/` | 解锁用户 |
| 系统管理 | GET | `/api/v1/accounts/permission-templates/` | 获取默认角色权限模板 |
| 系统管理 | GET/POST | `/api/v1/accounts/roles/` | 角色列表/创建 |
| 系统管理 | GET/PUT/PATCH | `/api/v1/accounts/roles/{id}/` | 角色详情/更新 |
| 系统管理 | GET/POST | `/api/v1/accounts/permissions/` | 权限项列表/创建 |
| 系统管理 | GET/PUT/PATCH | `/api/v1/accounts/permissions/{id}/` | 权限项详情/更新 |
| 系统管理 | GET/POST | `/api/v1/accounts/users/` | 用户列表/创建 |
| 系统管理 | GET/PUT/PATCH | `/api/v1/accounts/users/{id}/` | 用户详情/更新 |
| 组织 | GET/POST | `/api/v1/organizations/departments/` | 部门列表/创建 |
| 组织 | GET/PUT/PATCH | `/api/v1/organizations/departments/{id}/` | 部门详情/更新 |
| 组织 | GET | `/api/v1/organizations/departments/tree/` | 部门树 |
| 系统 | GET | `/api/v1/system/dashboard/` | 工作台 |
| 系统 | GET | `/api/v1/system/health/` | 健康检查 |
| 系统 | GET | `/api/v1/system/health/detail/` | 健康详情 |
| 档案 | GET/POST | `/api/v1/archives/storage-locations/` | 实体位置列表/创建 |
| 档案 | GET/PUT/PATCH | `/api/v1/archives/storage-locations/{id}/` | 实体位置详情/更新 |
| 档案 | GET/POST | `/api/v1/archives/records/` | 档案列表/创建 |
| 档案 | GET/PUT/PATCH | `/api/v1/archives/records/{id}/` | 档案详情/更新 |
| 档案 | POST | `/api/v1/archives/records/{id}/generate-codes/` | 生成条码/二维码 |
| 档案 | POST | `/api/v1/archives/records/{id}/print-codes/` | 打印留痕 |
| 档案 | POST | `/api/v1/archives/records/batch-print-codes/` | 批量打印留痕 |
| 档案 | POST | `/api/v1/archives/records/{id}/transition-status/` | 档案状态流转 |
| 档案 | POST | `/api/v1/archives/files/{file_id}/preview-ticket/` | 签发预览票据 |
| 档案 | POST | `/api/v1/archives/files/{file_id}/download-ticket/` | 签发下载票据 |
| 档案 | GET | `/api/v1/archives/file-access/{token}/content/` | 按票据获取文件内容 |
| 数字化 | GET/POST | `/api/v1/digitization/scan-tasks/` | 扫描任务列表/创建 |
| 数字化 | GET | `/api/v1/digitization/scan-tasks/{id}/` | 扫描任务详情 |
| 数字化 | GET | `/api/v1/digitization/scan-task-assignees/` | 扫描执行人列表 |
| 数字化 | POST | `/api/v1/digitization/scan-task-items/{item_id}/upload-files/` | 上传扫描文件 |
| 借阅 | GET/POST | `/api/v1/borrowing/applications/` | 借阅申请列表/创建 |
| 借阅 | GET | `/api/v1/borrowing/applications/{id}/` | 借阅申请详情 |
| 借阅 | POST | `/api/v1/borrowing/applications/{id}/approve/` | 借阅审批 |
| 借阅 | POST | `/api/v1/borrowing/applications/{id}/checkout/` | 出库登记 |
| 借阅 | POST | `/api/v1/borrowing/applications/{id}/submit-return/` | 提交归还 |
| 借阅 | POST | `/api/v1/borrowing/applications/{id}/confirm-return/` | 确认归还 |
| 借阅 | POST | `/api/v1/borrowing/reminders/dispatch/` | 手工触发催还 |
| 通知 | GET | `/api/v1/notifications/messages/` | 通知列表 |
| 通知 | GET | `/api/v1/notifications/messages/{id}/` | 通知详情 |
| 通知 | POST | `/api/v1/notifications/messages/mark-all-read/` | 全部已读 |
| 通知 | POST | `/api/v1/notifications/messages/{id}/mark-read/` | 单条已读 |
| 通知 | GET | `/api/v1/notifications/messages/{id}/position/` | 定位通知所在页 |
| 通知 | GET | `/api/v1/notifications/summary/` | 通知汇总 |
| 销毁 | GET/POST | `/api/v1/destruction/applications/` | 销毁申请列表/创建 |
| 销毁 | GET | `/api/v1/destruction/applications/{id}/` | 销毁申请详情 |
| 销毁 | POST | `/api/v1/destruction/applications/{id}/approve/` | 销毁审批 |
| 销毁 | POST | `/api/v1/destruction/applications/{id}/execute/` | 销毁执行 |
| 审计 | GET | `/api/v1/audit/logs/` | 审计日志列表 |
| 审计 | GET | `/api/v1/audit/logs/{id}/` | 审计日志详情 |
| 审计 | GET | `/api/v1/audit/summary/` | 审计汇总 |
| 报表 | GET | `/api/v1/reports/summary/` | 报表汇总 |
| 报表 | GET | `/api/v1/reports/departments/` | 部门借阅报表 |
| 报表 | GET | `/api/v1/reports/archives/` | 档案利用率报表 |
| 报表 | GET | `/api/v1/reports/export/` | 导出 CSV |

## 3. 认证模块

### 3.1 POST `/api/v1/auth/login/`

用途：用户名密码登录。

认证：无。

请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `username` | string | 是 | 用户名，最大 64 位 |
| `password` | string | 是 | 密码，最大 128 位 |

成功响应 `200`：

```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "tokens": {
      "access": "jwt-access-token",
      "refresh": "jwt-refresh-token"
    },
    "profile": {
      "id": 1,
      "username": "admin",
      "real_name": "系统管理员",
      "dept_id": 1,
      "dept_name": "总部",
      "security_clearance_level": "TOP_SECRET",
      "status": true,
      "roles": [],
      "permissions": []
    }
  }
}
```

失败响应：

- `400`：用户名不存在，或密码错误且未锁定
- `403`：账号已停用
- `423`：连续输错 3 次后锁定 15 分钟

### 3.2 POST `/api/v1/auth/logout/`

用途：主动退出登录并写审计日志。

认证：已登录。

成功响应：`200`

### 3.3 POST `/api/v1/auth/refresh/`

用途：用刷新令牌续签访问令牌。

认证：无。

请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `refresh` | string | 是 | 刷新令牌 |

成功响应：返回新的 `access`。

失败响应：

- `401`：刷新令牌无效或过期
- `403`：刷新令牌对应账号已停用

### 3.4 GET `/api/v1/auth/profile/`

用途：获取当前登录用户资料。

认证：已登录。

响应字段：

- `id`
- `username`
- `real_name`
- `email`
- `phone`
- `dept_id`
- `dept_name`
- `security_clearance_level`
- `status`
- `roles`
- `permissions`

### 3.5 POST `/api/v1/auth/unlock/{user_id}/`

用途：管理员或拥有用户管理权限的人员解锁账号。

认证：需要 `button.system.user.manage` 或 `ADMIN`。

路径参数：

- `user_id`：用户 ID

成功响应：`200`

失败响应：

- `404`：用户不存在
- `403`：无权限

## 4. 系统管理模块

### 4.1 GET `/api/v1/accounts/permission-templates/`

用途：返回内置角色权限模板，用于前端权限模板面板。

认证：需要角色管理权限。

### 4.2 角色接口

#### GET `/api/v1/accounts/roles/`

查询参数：

- `search`：按 `role_code`、`role_name` 模糊检索
- `ordering`：支持 `id`、`created_at`
- 分页参数：`paginate`、`page`、`page_size`

返回对象字段：

- `id`
- `role_code`
- `role_name`
- `data_scope`
- `status`
- `remark`
- `permission_ids`
- `permissions`
- `created_at`
- `updated_at`

#### POST `/api/v1/accounts/roles/`

请求体关键字段：

- `role_code`
- `role_name`
- `data_scope`
- `status`
- `remark`
- `permission_ids`

#### GET `/api/v1/accounts/roles/{id}/`

返回单个角色详情。

#### PUT/PATCH `/api/v1/accounts/roles/{id}/`

用途：更新角色基础属性和权限集合。

### 4.3 权限项接口

#### GET `/api/v1/accounts/permissions/`

查询参数：

- `search`：按 `permission_code`、`permission_name`、`module_name`
- `ordering`：支持 `sort_order`、`id`、`created_at`
- 分页参数

返回字段：

- `id`
- `parent_id`
- `parent_name`
- `permission_code`
- `permission_name`
- `permission_type`
- `module_name`
- `route_path`
- `sort_order`
- `status`
- `created_at`
- `updated_at`

#### POST `/api/v1/accounts/permissions/`

请求体关键字段：

- `parent_id`
- `permission_code`
- `permission_name`
- `permission_type`
- `module_name`
- `route_path`
- `sort_order`
- `status`

校验规则：

- 上级权限不能指向自己
- 上级权限不能指向当前权限的下级节点

#### GET/PUT/PATCH `/api/v1/accounts/permissions/{id}/`

用途：查看或更新权限项。

### 4.4 用户接口

#### GET `/api/v1/accounts/users/`

查询参数：

- `search`：按 `username`、`real_name`、`email`
- `ordering`：支持 `id`、`created_at`、`last_login_at`
- 分页参数

返回字段：

- `id`
- `dept_id`
- `dept_name`
- `username`
- `real_name`
- `email`
- `phone`
- `security_clearance_level`
- `status`
- `failed_login_count`
- `last_failed_login_at`
- `lock_until_at`
- `last_login_at`
- `last_login_ip`
- `remark`
- `is_staff`
- `role_ids`
- `roles`
- `created_at`
- `updated_at`

#### POST `/api/v1/accounts/users/`

请求体关键字段：

- `dept_id`
- `username`
- `password`
- `real_name`
- `email`
- `phone`
- `security_clearance_level`
- `status`
- `remark`
- `is_staff`
- `role_ids`

#### GET `/api/v1/accounts/users/{id}/`

返回用户详情。

#### PUT/PATCH `/api/v1/accounts/users/{id}/`

用途：更新用户资料、状态、角色，`password` 传入时会重置密码。

## 5. 组织模块

### 5.1 GET `/api/v1/organizations/departments/`

用途：部门列表。

认证：已登录。

查询参数：

- `search`：`dept_code`、`dept_name`
- `ordering`：`sort_order`、`created_at`、`id`
- 分页参数

返回字段：

- `id`
- `parent_id`
- `parent_name`
- `dept_code`
- `dept_name`
- `dept_path`
- `dept_level`
- `sort_order`
- `approver_user_id`
- `approver_user_name`
- `status`
- `remark`
- `created_at`
- `updated_at`

### 5.2 POST `/api/v1/organizations/departments/`

认证：需要 `button.system.department.manage` 或 `ADMIN`。

请求体关键字段：

- `parent_id`
- `dept_code`
- `dept_name`
- `sort_order`
- `approver_user_id`
- `status`
- `remark`

校验规则：

- 审批负责人必须存在且状态有效
- 上级部门不能是自己
- 上级部门不能是当前部门的下级

### 5.3 GET `/api/v1/organizations/departments/{id}/`

用途：部门详情。

### 5.4 PUT/PATCH `/api/v1/organizations/departments/{id}/`

用途：更新部门。

### 5.5 GET `/api/v1/organizations/departments/tree/`

用途：返回完整部门树结构。

认证：已登录。

## 6. 系统模块

### 6.1 GET `/`

用途：根健康检查。

认证：无。

响应字段：

- `service`
- `status`
- `time`
- `version`
- `message`

### 6.2 GET `/api/v1/system/health/`

用途：标准健康检查。

认证：无。

返回字段：

- `service`
- `status`
- `time`
- `version`

### 6.3 GET `/api/v1/system/health/detail/`

用途：查看数据库、Redis、存储健康详情。

认证：需要 `button.system.health.detail` 或 `ADMIN`。

返回字段：

- `service`
- `status`
- `time`
- `version`
- `checks.database`
- `checks.redis`
- `checks.storage`

状态说明：

- `ok`
- `warning`
- `error`

### 6.4 GET `/api/v1/system/dashboard/`

用途：工作台数据。

认证：已登录。

返回内容按角色动态裁剪，核心包括：

- `identity`
- `sections`
- `trends`
- `todo_items`
- `recent_notifications`

借阅人视图与管理/档案人员视图不同。

## 7. 档案模块

### 7.1 实体位置

#### GET `/api/v1/archives/storage-locations/`

查询参数：

- `search`：仓库、区域、柜号、架号、盒号、完整位置编码
- `warehouse_name`
- `cabinet_code`
- `status`
- `ordering`：`created_at`、`updated_at`、`id`
- 分页参数

返回字段：

- `id`
- `warehouse_name`
- `area_name`
- `cabinet_code`
- `rack_code`
- `layer_code`
- `box_code`
- `full_location_code`
- `status`
- `remark`
- `created_by`
- `updated_by`
- `created_at`
- `updated_at`

#### POST `/api/v1/archives/storage-locations/`

认证：需要 `button.location.manage` 或档案管理员角色。

请求体：

- `warehouse_name`
- `area_name`
- `cabinet_code`
- `rack_code`
- `layer_code`
- `box_code`
- `status`
- `remark`

#### GET/PUT/PATCH `/api/v1/archives/storage-locations/{id}/`

用途：查看或更新实体位置。

### 7.2 档案主数据

#### GET `/api/v1/archives/records/`

用途：档案检索与列表查看。

查询参数：

- `keyword` 或 `search`
- `archive_code`
- `year`
- `retention_period`
- `security_level`
- `status`
- `responsible_dept_id`
- `location_id`
- `ordering`：`id`、`created_at`、`updated_at`、`year`
- 分页参数

返回字段：

- `id`
- `archive_code`
- `title`
- `year`
- `retention_period`
- `security_level`
- `status`
- `responsible_dept_id`
- `responsible_dept_name`
- `responsible_person`
- `formed_at`
- `keywords`
- `summary`
- `page_count`
- `carrier_type`
- `location_id`
- `location_detail`
- `current_borrow_id`
- `catalog_completed_at`
- `shelved_at`
- `is_sensitive_masked`
- `masked_fields`
- `created_by`
- `updated_by`
- `created_at`
- `updated_at`

脱敏说明：

- 若当前用户无权查看敏感字段，则：
  - `is_sensitive_masked=true`
  - `masked_fields` 标记被脱敏字段
  - `summary`、`responsible_person`、`location_detail`、`files` 按规则隐藏

#### POST `/api/v1/archives/records/`

认证：需要 `button.archive.create` 或档案管理员角色。

请求体关键字段：

- `archive_code`
- `title`
- `year`
- `retention_period`
- `security_level`
- `responsible_dept_id`
- `responsible_person`
- `formed_at`
- `keywords`
- `summary`
- `page_count`
- `carrier_type`
- `location_id`
- `revision_remark`

校验规则：

- `formed_at` 的年份必须与 `year` 一致

#### GET `/api/v1/archives/records/{id}/`

返回列表字段外，还会补充：

- `barcodes`
- `revisions`
- `files`

#### PUT/PATCH `/api/v1/archives/records/{id}/`

认证：需要 `button.archive.edit`。

用途：更新档案主数据并生成修订记录。

### 7.3 档案动作接口

#### POST `/api/v1/archives/records/{id}/generate-codes/`

用途：生成条码和二维码。

认证：需要 `button.archive.generate_code`。

#### POST `/api/v1/archives/records/{id}/print-codes/`

用途：记录单个档案打印留痕。

认证：需要 `button.archive.print`。

#### POST `/api/v1/archives/records/batch-print-codes/`

用途：批量打印留痕。

请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `archive_ids` | integer[] | 是 | 档案 ID 列表，去重后最多 50 条 |

#### POST `/api/v1/archives/records/{id}/transition-status/`

用途：档案状态流转。

请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `next_status` | string | 是 | 目标状态 |
| `current_borrow_id` | integer | 否 | 状态与借阅关联时使用 |
| `remark` | string | 否 | 流转说明 |

### 7.4 文件访问票据

#### POST `/api/v1/archives/files/{file_id}/preview-ticket/`

用途：签发预览票据。

认证：已登录。

返回字段：

- `access_url`
- `watermark_text`
- `expires_at`
- `file_name`
- `file_ext`

#### POST `/api/v1/archives/files/{file_id}/download-ticket/`

用途：签发下载票据。

认证：已登录。

请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `purpose` | string | 是 | 下载用途，最大 255 位 |

返回字段：

- `access_url`
- `expires_at`
- `file_name`
- `purpose`

#### GET `/api/v1/archives/file-access/{token}/content/`

用途：按票据读取文件二进制内容。

认证：票据即可，无需登录。

返回类型：

- 预览：文件流
- 下载：附件流

失败响应：

- `400`：票据无效或过期
- `404`：文件已不存在

## 8. 数字化模块

### 8.1 GET `/api/v1/digitization/scan-tasks/`

查询参数：

- `search`：`task_no`、`task_name`、`remark`
- `status`
- `assigned_user_id`
- `ordering`：`id`、`created_at`、`started_at`、`finished_at`
- 分页参数

返回字段：

- `id`
- `task_no`
- `task_name`
- `assigned_user_id`
- `assigned_user_name`
- `assigned_by`
- `status`
- `total_count`
- `completed_count`
- `failed_count`
- `started_at`
- `finished_at`
- `remark`
- `created_by`
- `updated_by`
- `created_at`
- `updated_at`

### 8.2 POST `/api/v1/digitization/scan-tasks/`

认证：需要 `button.scan_task.manage` 或档案管理员。

请求体：

- `task_name`
- `assigned_user_id`
- `archive_ids`
- `remark`

校验规则：

- `assigned_user_id` 必须是启用状态的在职员工

### 8.3 GET `/api/v1/digitization/scan-tasks/{id}/`

返回字段额外包含：

- `items`
- `items[].files`
- `items[].uploaded_file_count`
- `items[].error_message`

### 8.4 GET `/api/v1/digitization/scan-task-assignees/`

用途：返回可分配的扫描执行人。

返回字段：

- `id`
- `username`
- `real_name`
- `dept_id`

### 8.5 POST `/api/v1/digitization/scan-task-items/{item_id}/upload-files/`

用途：为扫描任务明细上传文件。

认证：需要 `button.scan_task.manage`。

请求类型：`multipart/form-data`

表单字段：

- `files`：可多文件上传，至少 1 个

成功响应：返回所属扫描任务详情。

## 9. 借阅模块

### 9.1 GET `/api/v1/borrowing/applications/`

用途：借阅申请列表。

查询参数：

- `scope`：`mine`、`approval`、`all` 等
- `keyword`
- `archive_code`
- `status`
- `status_in`
- `archive_id`
- `applicant_id`
- `applicant_dept_id`
- `current_approver_id`
- `is_overdue`
- `ordering`
- 分页参数

返回字段：

- `id`
- `application_no`
- `archive_id`
- `archive_code`
- `archive_title`
- `archive_status`
- `archive_security_level`
- `applicant_id`
- `applicant_name`
- `applicant_dept_id`
- `applicant_dept_name`
- `purpose`
- `expected_return_at`
- `status`
- `current_approver_id`
- `current_approver_name`
- `submitted_at`
- `approved_at`
- `rejected_at`
- `checkout_at`
- `returned_at`
- `reject_reason`
- `is_overdue`
- `overdue_days`
- `return_status`
- `can_approve`
- `can_checkout`
- `can_submit_return`
- `can_confirm_return`
- `created_by`
- `updated_by`
- `created_at`
- `updated_at`

### 9.2 POST `/api/v1/borrowing/applications/`

认证：需要 `button.borrow.create`。

请求体：

- `archive_id`
- `purpose`
- `expected_return_at`

### 9.3 GET `/api/v1/borrowing/applications/{id}/`

返回列表字段外，还会补充：

- `approval_records`
- `checkout_record`
- `return_record`

### 9.4 POST `/api/v1/borrowing/applications/{id}/approve/`

认证：需要 `button.borrow.approve`。

请求体：

- `action`：审批动作
- `opinion`

规则：

- 驳回时必须填写 `opinion`

### 9.5 POST `/api/v1/borrowing/applications/{id}/checkout/`

认证：需要 `button.borrow.checkout`。

请求体：

- `checkout_note`

### 9.6 POST `/api/v1/borrowing/applications/{id}/submit-return/`

认证：需要 `button.borrow.return.submit`。

请求类型：`multipart/form-data`

表单字段：

- `handover_note`
- `photo_files`：可多文件
- `handover_files`：可多文件

规则：

- `photo_files` 与 `handover_files` 至少上传一种

### 9.7 POST `/api/v1/borrowing/applications/{id}/confirm-return/`

认证：需要 `button.borrow.return.confirm`。

请求体：

- `approved`：是否确认归还通过
- `location_after_return_id`
- `confirm_note`

### 9.8 POST `/api/v1/borrowing/reminders/dispatch/`

用途：手工触发催还扫描。

认证：需要 `button.notification.reminder.dispatch`。

返回字段：

- `record_count`

## 10. 通知模块

### 10.1 GET `/api/v1/notifications/messages/`

用途：当前登录用户的通知列表。

查询参数：

- `notification_type`
- `is_read`：`true` / `false`
- `ordering`
- 分页参数

返回字段：

- `id`
- `notification_type`
- `title`
- `content`
- `biz_type`
- `biz_id`
- `is_read`
- `read_at`
- `created_at`
- `updated_at`
- `route_path`

### 10.2 GET `/api/v1/notifications/messages/{id}/`

用途：通知详情。

### 10.3 POST `/api/v1/notifications/messages/mark-all-read/`

用途：全部标记为已读。

返回字段：

- `updated_count`

### 10.4 POST `/api/v1/notifications/messages/{id}/mark-read/`

用途：单条标记已读。

返回字段：通知详情。

### 10.5 GET `/api/v1/notifications/messages/{id}/position/`

用途：计算某条通知位于第几页。

查询参数：

- `page_size`：默认 8，范围 1 到 200

### 10.6 GET `/api/v1/notifications/summary/`

用途：通知汇总。

返回典型字段：

- `total_count`
- `unread_count`
- `type_breakdown`
- `latest_items`

## 11. 销毁模块

### 11.1 GET `/api/v1/destruction/applications/`

查询参数：

- `scope`：`mine`、`approval`、`execution`、`all`
- `keyword`
- `status`
- `archive_code`
- `archive_id`
- `applicant_id`
- `applicant_dept_id`
- `current_approver_id`
- `ordering`
- 分页参数

返回字段：

- `id`
- `application_no`
- `archive_id`
- `archive_code`
- `archive_title`
- `archive_status`
- `archive_security_level`
- `applicant_id`
- `applicant_name`
- `applicant_dept_id`
- `applicant_dept_name`
- `reason`
- `basis`
- `status`
- `current_approver_id`
- `current_approver_name`
- `submitted_at`
- `approved_at`
- `rejected_at`
- `executed_at`
- `reject_reason`
- `can_approve`
- `can_execute`
- `created_by`
- `updated_by`
- `created_at`
- `updated_at`

### 11.2 POST `/api/v1/destruction/applications/`

认证：需要 `button.destruction.create`。

请求体：

- `archive_id`
- `reason`
- `basis`

### 11.3 GET `/api/v1/destruction/applications/{id}/`

返回列表字段外，补充：

- `approval_records`
- `execution_record`

### 11.4 POST `/api/v1/destruction/applications/{id}/approve/`

认证：需要 `button.destruction.approve`。

请求体：

- `action`
- `opinion`

规则：

- 驳回时必须填写 `opinion`

### 11.5 POST `/api/v1/destruction/applications/{id}/execute/`

认证：需要 `button.destruction.execute`。

请求类型：`multipart/form-data`

表单字段：

- `execution_note`
- `attachment_files`

返回字段：完整销毁申请详情。

## 12. 审计模块

### 12.1 GET `/api/v1/audit/logs/`

认证：需要审计查看权限。

查询参数：

- `keyword`
- `module_name`
- `action_code`
- `result_status`
- `username`
- `biz_type`
- `ordering`
- 分页参数

返回字段：

- `id`
- `user_id`
- `username`
- `real_name`
- `module_name`
- `action_code`
- `biz_type`
- `biz_id`
- `target_repr`
- `result_status`
- `description`
- `ip_address`
- `user_agent`
- `request_method`
- `request_path`
- `extra_data_json`
- `created_at`

### 12.2 GET `/api/v1/audit/logs/{id}/`

用途：查看单条审计日志详情。

### 12.3 GET `/api/v1/audit/summary/`

用途：获取审计概览统计。

## 13. 报表模块

### 13.1 公共过滤参数

以下报表接口共用：

- `start_date`
- `end_date`
- `applicant_dept_id`
- `archive_security_level`
- `archive_status`
- `carrier_type`

校验规则：

- `start_date` 不能晚于 `end_date`

### 13.2 GET `/api/v1/reports/summary/`

用途：报表总览。

认证：需要报表查看权限。

### 13.3 GET `/api/v1/reports/departments/`

用途：部门借阅统计。

返回典型字段：

- `applicant_dept_id`
- `applicant_dept_name`
- `borrow_count`
- `overdue_count`
- `returned_count`
- `overdue_rate`

### 13.4 GET `/api/v1/reports/archives/`

用途：档案利用率统计。

返回典型字段：

- `rank`
- `archive_id`
- `archive_code`
- `archive_title`
- `security_level`
- `status`
- `carrier_type`
- `borrow_count`
- `overdue_count`
- `returned_count`
- `latest_borrowed_at`

### 13.5 GET `/api/v1/reports/export/`

用途：导出报表 CSV。

认证：需要报表查看权限。

查询参数：

- 上述公共过滤参数
- `report_type`：`departments` 或 `archives`

返回类型：

- `text/csv; charset=utf-8`

说明：

- 导出行为会记录审计日志
- 导出成功后会为当前用户创建一条系统通知

## 14. 常见错误码

| HTTP / code | 说明 |
| --- | --- |
| `200` | 查询或操作成功 |
| `201` | 创建成功 |
| `400` | 参数错误、业务校验失败、票据无效等 |
| `401` | 未认证或令牌失效 |
| `403` | 已认证但无权限 |
| `404` | 目标资源不存在 |
| `423` | 登录锁定 |

## 15. 测试与验收建议

建议验收时至少覆盖以下路径：

1. 管理员登录、刷新令牌、退出登录
2. 用户/角色/权限/部门增改查
3. 档案创建、编辑、条码生成、状态流转、文件票据访问
4. 借阅申请、审批、出库、归还、催还
5. 销毁申请、审批、执行
6. 扫描任务创建、文件上传
7. 通知列表、已读、定位
8. 审计日志与报表导出
9. 健康检查、健康详情鉴权

如需对应自动化执行，可结合 `fullstack/scripts/run_tests.sh` 与 `fullstack/tests/` 目录下的测试清单运行。
