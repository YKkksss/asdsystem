# 岚仓档案数字化与流转系统数据库设计文档

## 1. 文档定位

本文档基于以下两份内容整理：

1. 原始项目需求描述 `prompt.md`
2. 现有开发文档 `岚仓档案数字化与流转系统开发文档.md`

文档目标是将业务需求落实到可直接建模的数据库层，覆盖：

1. MySQL 核心表结构设计
2. 表间关系与关键约束
3. 状态枚举与字段约定
4. 索引设计
5. Redis 键设计

本文档只围绕当前项目需求进行设计，不引入与项目描述无关的扩展能力。

## 2. 设计依据与关键约定

## 2.1 设计依据

项目需求明确包含以下核心能力：

1. 组织架构与角色权限管理。
2. 登录失败 3 次锁定 15 分钟。
3. 纸质档案入库、条码/二维码生成、柜架位置管理。
4. 扫描任务分配、批量上传 PDF/图片、自动缩略图。
5. 编目字段校验：档号、题名、年度、保管期限、密级。
6. 全文检索与字段组合筛选，按密级隐藏敏感字段。
7. 借阅申请、领导审批、出入库登记、超期催还、归还拍照或上传交接单。
8. 销毁申请、审批、执行留痕。
9. 借阅次数、超期率、利用率报表与导出。
10. 在线预览水印、下载二次确认、用途记录。
11. 所有关键操作写入不可修改审计日志。

## 2.2 关键业务约定

以下约定来自现有需求理解，用于消除建模歧义：

1. 借阅审批采用单层审批，审批人由申请人所属部门的审批负责人承担。
2. 一张借阅申请单只对应一份档案。
3. 归还凭证支持“照片”或“交接单”，至少上传一种。
4. 全文检索优先覆盖编目字段和电子原生 PDF 提取文本；图片扫描件不做 OCR。
5. 条码与二维码均围绕档号生成。
6. 审计日志只允许新增，不允许更新和删除。

## 3. 数据库总体设计

## 3.1 技术选型

1. 关系型数据库：MySQL 8.0+
2. 缓存与短期状态存储：Redis 7+
3. 存储引擎：InnoDB
4. 字符集：`utf8mb4`
5. 排序规则：`utf8mb4_unicode_ci`

## 3.2 命名规范

1. 表名统一使用小写下划线风格。
2. 主键统一使用 `id`，类型为 `bigint unsigned`。
3. 外键字段统一使用 `{实体}_id` 命名。
4. 时间字段统一使用：
   - `created_at`
   - `updated_at`
5. 人员字段统一使用：
   - `created_by`
   - `updated_by`
6. 状态字段统一使用 `status`。
7. 是否型字段统一使用 `is_` 前缀。

## 3.3 通用字段约定

除审计日志类表以外，业务主表推荐统一包含以下审计字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `created_by` | bigint unsigned | 创建人 ID |
| `created_at` | datetime | 创建时间 |
| `updated_by` | bigint unsigned | 最后更新人 ID |
| `updated_at` | datetime | 最后更新时间 |

说明：

1. 纯关系表可只保留 `created_at`。
2. 审计日志表只保留写入时间，不保留更新字段。
3. 不在数据库层为所有表强制设计逻辑删除字段，业务数据默认不做物理删除。

## 4. 枚举与状态约定

## 4.1 角色编码

| 编码 | 名称 |
| --- | --- |
| `ADMIN` | 管理员 |
| `ARCHIVIST` | 档案员 |
| `BORROWER` | 借阅人 |
| `AUDITOR` | 审计员 |

## 4.2 数据权限范围

| 编码 | 说明 |
| --- | --- |
| `SELF` | 仅本人 |
| `DEPT` | 仅本部门 |
| `DEPT_AND_CHILD` | 本部门及子部门 |
| `ALL` | 全部 |

## 4.3 密级

| 编码 | 名称 | 排序值 |
| --- | --- | --- |
| `PUBLIC` | 公开 | 1 |
| `INTERNAL` | 内部 | 2 |
| `SECRET` | 秘密 | 3 |
| `CONFIDENTIAL` | 机密 | 4 |
| `TOP_SECRET` | 绝密 | 5 |

## 4.4 档案状态

| 编码 | 说明 |
| --- | --- |
| `DRAFT` | 草稿 |
| `PENDING_SCAN` | 待扫描 |
| `PENDING_CATALOG` | 待编目 |
| `ON_SHELF` | 已上架 |
| `BORROWED` | 借出中 |
| `DESTROY_PENDING` | 销毁审批中 |
| `DESTROYED` | 已销毁 |
| `FROZEN` | 冻结 |

## 4.5 扫描任务状态

| 编码 | 说明 |
| --- | --- |
| `PENDING` | 待处理 |
| `PROCESSING` | 处理中 |
| `COMPLETED` | 已完成 |
| `FAILED` | 失败 |

## 4.6 文件处理任务状态

| 编码 | 说明 |
| --- | --- |
| `PENDING` | 待处理 |
| `RUNNING` | 处理中 |
| `SUCCESS` | 成功 |
| `FAILED` | 失败 |

## 4.7 借阅申请状态

| 编码 | 说明 |
| --- | --- |
| `DRAFT` | 草稿 |
| `PENDING_APPROVAL` | 待审批 |
| `APPROVED` | 已通过 |
| `REJECTED` | 已驳回 |
| `WITHDRAWN` | 已撤回 |
| `CHECKED_OUT` | 借出中 |
| `OVERDUE` | 已超期 |
| `RETURNED` | 已归还 |

## 4.8 归还确认状态

| 编码 | 说明 |
| --- | --- |
| `SUBMITTED` | 已提交归还 |
| `CONFIRMED` | 已确认入库 |
| `REJECTED` | 归还验收不通过 |

## 4.9 催还类型

| 编码 | 说明 |
| --- | --- |
| `BEFORE_DUE` | 到期前提醒 |
| `DUE_TODAY` | 到期当天提醒 |
| `OVERDUE` | 超期提醒 |

## 4.10 销毁申请状态

| 编码 | 说明 |
| --- | --- |
| `PENDING_APPROVAL` | 待审批 |
| `APPROVED` | 已审批通过 |
| `REJECTED` | 已驳回 |
| `EXECUTED` | 已执行销毁 |

## 4.11 通知类型

| 编码 | 说明 |
| --- | --- |
| `BORROW_APPROVAL` | 借阅审批通知 |
| `BORROW_REMINDER` | 催还通知 |
| `RETURN_CONFIRM` | 归还确认通知 |
| `DESTROY_APPROVAL` | 销毁审批通知 |
| `SYSTEM` | 系统通知 |

## 5. 模块关系总览

## 5.1 组织与权限

1. `org_department` 通过 `parent_id` 构成组织树。
2. `sys_user.dept_id` 指向所属部门。
3. `sys_user_role` 建立用户与角色多对多关系。
4. `sys_role_permission` 建立角色与权限多对多关系。

## 5.2 档案与位置

1. `archive_record.location_id` 指向实体位置。
2. `archive_barcode.archive_id` 指向档案主表。
3. `archive_file.archive_id` 指向档案主表。
4. `archive_metadata_revision.archive_id` 指向档案主表。

## 5.3 数字化

1. `scan_task_item.task_id` 指向扫描任务。
2. `scan_task_item.archive_id` 指向档案主表。
3. `file_process_job.archive_file_id` 指向档案文件表。

## 5.4 借阅

1. `borrow_application.archive_id` 指向档案主表。
2. `borrow_approval_record.application_id` 指向借阅申请。
3. `borrow_checkout_record.application_id` 指向借阅申请。
4. `borrow_return_record.application_id` 指向借阅申请。
5. `borrow_return_attachment.return_record_id` 指向归还记录。
6. `borrow_reminder_record.application_id` 指向借阅申请。

## 5.5 销毁

1. `destroy_application.archive_id` 指向档案主表。
2. `destroy_approval_record.application_id` 指向销毁申请。
3. `destroy_execution_record.application_id` 指向销毁申请。
4. `destroy_attachment.application_id` 指向销毁申请。

## 5.6 日志与通知

1. `sys_notification.user_id` 指向用户。
2. `preview_log`、`download_log`、`audit_log` 均保留用户与目标对象快照。
3. `sys_email_task` 与催还、审批等业务记录按 `biz_type + biz_id` 建关联。

## 6. MySQL 详细表设计

## 6.1 组织与权限模块

### 6.1.1 `org_department` 部门表

用途：维护组织树和审批负责人。

核心约束：

1. `dept_code` 全局唯一。
2. `parent_id` 允许为空，表示根部门。
3. `approver_user_id` 指向部门审批负责人。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `parent_id` | bigint unsigned | 否 | null | IDX | 上级部门 ID |
| `dept_code` | varchar(64) | 是 | - | UK | 部门编码 |
| `dept_name` | varchar(100) | 是 | - | IDX | 部门名称 |
| `dept_path` | varchar(500) | 是 | - | - | 层级路径，如 `/1/3/8` |
| `dept_level` | int unsigned | 是 | 1 | - | 层级深度 |
| `sort_order` | int | 是 | 0 | - | 排序值 |
| `approver_user_id` | bigint unsigned | 否 | null | IDX | 借阅审批负责人 |
| `status` | tinyint | 是 | 1 | IDX | 1 启用，0 停用 |
| `remark` | varchar(255) | 否 | null | - | 备注 |
| `created_by` | bigint unsigned | 否 | null | - | 创建人 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |
| `updated_by` | bigint unsigned | 否 | null | - | 更新人 |
| `updated_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 更新时间 |

### 6.1.2 `sys_user` 用户表

用途：系统登录用户、审批人、借阅人、档案员统一用户表。

核心约束：

1. `username` 唯一。
2. 登录失败锁定信息保留在 MySQL，实时锁定状态以 Redis 为准。
3. 邮箱建议填写，用于超期邮件提醒。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `dept_id` | bigint unsigned | 是 | - | IDX | 所属主部门 |
| `username` | varchar(64) | 是 | - | UK | 登录账号 |
| `password_hash` | varchar(255) | 是 | - | - | 密码哈希 |
| `real_name` | varchar(100) | 是 | - | IDX | 真实姓名 |
| `email` | varchar(128) | 否 | null | IDX | 邮箱 |
| `phone` | varchar(32) | 否 | null | - | 手机号 |
| `security_clearance_level` | varchar(16) | 是 | `INTERNAL` | IDX | 可访问的最高密级 |
| `status` | tinyint | 是 | 1 | IDX | 1 启用，0 停用 |
| `failed_login_count` | int unsigned | 是 | 0 | - | 累计连续失败次数 |
| `last_failed_login_at` | datetime | 否 | null | - | 最后一次失败时间 |
| `lock_until_at` | datetime | 否 | null | - | 锁定截止时间 |
| `last_login_at` | datetime | 否 | null | - | 最后登录时间 |
| `last_login_ip` | varchar(64) | 否 | null | - | 最后登录 IP |
| `remark` | varchar(255) | 否 | null | - | 备注 |
| `created_by` | bigint unsigned | 否 | null | - | 创建人 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |
| `updated_by` | bigint unsigned | 否 | null | - | 更新人 |
| `updated_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 更新时间 |

### 6.1.3 `sys_role` 角色表

用途：定义管理员、档案员、借阅人、审计员等角色。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `role_code` | varchar(64) | 是 | - | UK | 角色编码 |
| `role_name` | varchar(100) | 是 | - | - | 角色名称 |
| `data_scope` | varchar(32) | 是 | `SELF` | - | 数据权限范围 |
| `status` | tinyint | 是 | 1 | IDX | 1 启用，0 停用 |
| `remark` | varchar(255) | 否 | null | - | 备注 |
| `created_by` | bigint unsigned | 否 | null | - | 创建人 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |
| `updated_by` | bigint unsigned | 否 | null | - | 更新人 |
| `updated_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 更新时间 |

### 6.1.4 `sys_permission` 权限表

用途：定义菜单、按钮、接口权限点。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `parent_id` | bigint unsigned | 否 | null | IDX | 上级权限 |
| `permission_code` | varchar(100) | 是 | - | UK | 权限编码 |
| `permission_name` | varchar(100) | 是 | - | - | 权限名称 |
| `permission_type` | varchar(32) | 是 | `MENU` | IDX | `MENU/BUTTON/API` |
| `module_name` | varchar(64) | 是 | - | IDX | 所属模块 |
| `route_path` | varchar(255) | 否 | null | - | 前端路由或接口路径 |
| `sort_order` | int | 是 | 0 | - | 排序值 |
| `status` | tinyint | 是 | 1 | IDX | 1 启用，0 停用 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |

### 6.1.5 `sys_user_role` 用户角色关联表

用途：建立用户与角色多对多关系。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `user_id` | bigint unsigned | 是 | - | UK(`user_id`,`role_id`) | 用户 ID |
| `role_id` | bigint unsigned | 是 | - | UK(`user_id`,`role_id`) | 角色 ID |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |

### 6.1.6 `sys_role_permission` 角色权限关联表

用途：建立角色与权限多对多关系。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `role_id` | bigint unsigned | 是 | - | UK(`role_id`,`permission_id`) | 角色 ID |
| `permission_id` | bigint unsigned | 是 | - | UK(`role_id`,`permission_id`) | 权限 ID |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |

## 6.2 档案与位置模块

### 6.2.1 `archive_storage_location` 实体位置表

用途：记录档案柜架位置，支持库房到盒位的完整定位。

核心约束：

1. `full_location_code` 唯一。
2. 一个位置默认对应一个盒位级定位点。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `warehouse_name` | varchar(100) | 是 | - | IDX | 库房名称 |
| `area_name` | varchar(100) | 否 | null | - | 分区名称 |
| `cabinet_code` | varchar(64) | 是 | - | IDX | 柜号 |
| `rack_code` | varchar(64) | 是 | - | - | 架号 |
| `layer_code` | varchar(64) | 是 | - | - | 层号 |
| `box_code` | varchar(64) | 是 | - | - | 盒号 |
| `full_location_code` | varchar(255) | 是 | - | UK | 完整位置编码 |
| `status` | tinyint | 是 | 1 | IDX | 1 可用，0 停用 |
| `remark` | varchar(255) | 否 | null | - | 备注 |
| `created_by` | bigint unsigned | 否 | null | - | 创建人 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |
| `updated_by` | bigint unsigned | 否 | null | - | 更新人 |
| `updated_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 更新时间 |

### 6.2.2 `archive_record` 档案主表

用途：纸质档案及其数字化主信息。

核心约束：

1. `archive_code` 唯一。
2. `档号、题名、年度、保管期限、密级` 为必填字段。
3. 当前借出状态由 `status` 与 `current_borrow_id` 联合体现。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `archive_code` | varchar(64) | 是 | - | UK | 档号 |
| `title` | varchar(255) | 是 | - | FULLTEXT/IDX | 题名 |
| `year` | smallint unsigned | 是 | - | IDX | 年度 |
| `retention_period` | varchar(32) | 是 | - | IDX | 保管期限 |
| `security_level` | varchar(16) | 是 | - | IDX | 密级 |
| `status` | varchar(32) | 是 | `DRAFT` | IDX | 档案状态 |
| `responsible_dept_id` | bigint unsigned | 否 | null | IDX | 责任部门 |
| `responsible_person` | varchar(100) | 否 | null | - | 责任人 |
| `formed_at` | date | 否 | null | - | 形成日期 |
| `keywords` | varchar(500) | 否 | null | FULLTEXT | 关键词 |
| `summary` | text | 否 | null | FULLTEXT | 摘要 |
| `page_count` | int unsigned | 否 | null | - | 页数 |
| `carrier_type` | varchar(32) | 否 | null | - | 载体类型 |
| `location_id` | bigint unsigned | 否 | null | IDX | 当前实体位置 |
| `current_borrow_id` | bigint unsigned | 否 | null | IDX | 当前借阅单 ID |
| `catalog_completed_at` | datetime | 否 | null | - | 编目完成时间 |
| `shelved_at` | datetime | 否 | null | - | 上架时间 |
| `created_by` | bigint unsigned | 否 | null | - | 创建人 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |
| `updated_by` | bigint unsigned | 否 | null | - | 更新人 |
| `updated_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 更新时间 |

### 6.2.3 `archive_metadata_revision` 编目修订表

用途：记录编目修改历史，满足留痕要求。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `archive_id` | bigint unsigned | 是 | - | IDX | 档案 ID |
| `revision_no` | int unsigned | 是 | - | UK(`archive_id`,`revision_no`) | 修订版本号 |
| `changed_fields_json` | json | 是 | - | - | 本次变更字段列表 |
| `snapshot_json` | json | 是 | - | - | 变更后完整快照 |
| `remark` | varchar(255) | 否 | null | - | 修订说明 |
| `revised_by` | bigint unsigned | 是 | - | IDX | 修订人 |
| `revised_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 修订时间 |

### 6.2.4 `archive_barcode` 条码二维码表

用途：存储档案条码和二维码生成结果及打印信息。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `archive_id` | bigint unsigned | 是 | - | IDX | 档案 ID |
| `code_type` | varchar(16) | 是 | - | IDX | `BARCODE/QRCODE` |
| `code_content` | varchar(255) | 是 | - | - | 编码内容 |
| `image_path` | varchar(500) | 否 | null | - | 图片路径 |
| `print_count` | int unsigned | 是 | 0 | - | 打印次数 |
| `last_printed_at` | datetime | 否 | null | - | 最后打印时间 |
| `created_by` | bigint unsigned | 否 | null | - | 创建人 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |

### 6.2.5 `archive_file` 档案文件表

用途：记录档案关联的 PDF/图片文件及缩略图、提取文本等信息。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `archive_id` | bigint unsigned | 是 | - | IDX | 档案 ID |
| `scan_task_item_id` | bigint unsigned | 否 | null | IDX | 扫描任务明细 ID |
| `file_name` | varchar(255) | 是 | - | - | 原始文件名 |
| `file_path` | varchar(500) | 是 | - | - | 文件路径 |
| `thumbnail_path` | varchar(500) | 否 | null | - | 缩略图路径 |
| `file_ext` | varchar(16) | 是 | - | IDX | 文件扩展名 |
| `mime_type` | varchar(64) | 否 | null | - | MIME 类型 |
| `file_size` | bigint unsigned | 是 | 0 | - | 文件大小，字节 |
| `page_count` | int unsigned | 否 | null | - | 页数 |
| `file_source` | varchar(32) | 是 | `SCAN_UPLOAD` | IDX | 文件来源 |
| `sort_order` | int | 是 | 0 | - | 排序值 |
| `extracted_text` | longtext | 否 | null | FULLTEXT | 提取文本 |
| `status` | varchar(16) | 是 | `ACTIVE` | IDX | 文件状态 |
| `uploaded_by` | bigint unsigned | 是 | - | IDX | 上传人 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 上传时间 |

## 6.3 数字化模块

### 6.3.1 `scan_task` 扫描任务表

用途：管理扫描任务分配与整体进度。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `task_no` | varchar(64) | 是 | - | UK | 任务编号 |
| `task_name` | varchar(200) | 是 | - | - | 任务名称 |
| `assigned_user_id` | bigint unsigned | 是 | - | IDX | 指派执行人 |
| `assigned_by` | bigint unsigned | 是 | - | IDX | 指派人 |
| `status` | varchar(16) | 是 | `PENDING` | IDX | 任务状态 |
| `total_count` | int unsigned | 是 | 0 | - | 档案总数 |
| `completed_count` | int unsigned | 是 | 0 | - | 完成数 |
| `failed_count` | int unsigned | 是 | 0 | - | 失败数 |
| `started_at` | datetime | 否 | null | - | 开始时间 |
| `finished_at` | datetime | 否 | null | - | 完成时间 |
| `remark` | varchar(255) | 否 | null | - | 备注 |
| `created_by` | bigint unsigned | 否 | null | - | 创建人 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |
| `updated_by` | bigint unsigned | 否 | null | - | 更新人 |
| `updated_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 更新时间 |

### 6.3.2 `scan_task_item` 扫描任务明细表

用途：任务中的单档案处理项。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `task_id` | bigint unsigned | 是 | - | IDX | 扫描任务 ID |
| `archive_id` | bigint unsigned | 是 | - | UK(`task_id`,`archive_id`) | 档案 ID |
| `assignee_user_id` | bigint unsigned | 是 | - | IDX | 执行人 |
| `status` | varchar(16) | 是 | `PENDING` | IDX | 明细状态 |
| `uploaded_file_count` | int unsigned | 是 | 0 | - | 已上传文件数 |
| `last_uploaded_at` | datetime | 否 | null | - | 最后上传时间 |
| `error_message` | varchar(500) | 否 | null | - | 异常说明 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |
| `updated_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 更新时间 |

### 6.3.3 `file_process_job` 文件处理任务表

用途：异步处理缩略图生成、文本提取等任务。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `archive_file_id` | bigint unsigned | 是 | - | IDX | 档案文件 ID |
| `job_type` | varchar(32) | 是 | - | IDX | `THUMBNAIL/TEXT_EXTRACT` |
| `status` | varchar(16) | 是 | `PENDING` | IDX | 处理状态 |
| `retry_count` | int unsigned | 是 | 0 | - | 重试次数 |
| `error_message` | varchar(500) | 否 | null | - | 错误信息 |
| `started_at` | datetime | 否 | null | - | 开始时间 |
| `finished_at` | datetime | 否 | null | - | 结束时间 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |

## 6.4 借阅模块

### 6.4.1 `borrow_application` 借阅申请表

用途：借阅申请主单。

核心约束：

1. 一张借阅申请只对应一份档案。
2. 预计归还时间必填。
3. 借阅用途必填。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `application_no` | varchar(64) | 是 | - | UK | 申请编号 |
| `archive_id` | bigint unsigned | 是 | - | IDX | 档案 ID |
| `applicant_id` | bigint unsigned | 是 | - | IDX | 申请人 |
| `applicant_dept_id` | bigint unsigned | 是 | - | IDX | 申请部门 |
| `purpose` | varchar(500) | 是 | - | - | 借阅用途 |
| `expected_return_at` | datetime | 是 | - | IDX | 预计归还时间 |
| `status` | varchar(32) | 是 | `DRAFT` | IDX | 借阅状态 |
| `current_approver_id` | bigint unsigned | 否 | null | IDX | 当前审批人 |
| `submitted_at` | datetime | 否 | null | - | 提交时间 |
| `approved_at` | datetime | 否 | null | - | 审批通过时间 |
| `rejected_at` | datetime | 否 | null | - | 驳回时间 |
| `withdrawn_at` | datetime | 否 | null | - | 撤回时间 |
| `checkout_at` | datetime | 否 | null | - | 实际借出时间 |
| `returned_at` | datetime | 否 | null | - | 实际归还时间 |
| `reject_reason` | varchar(255) | 否 | null | - | 驳回原因 |
| `is_overdue` | tinyint | 是 | 0 | IDX | 是否超期 |
| `overdue_days` | int unsigned | 是 | 0 | - | 超期天数 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |
| `updated_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 更新时间 |

### 6.4.2 `borrow_approval_record` 借阅审批记录表

用途：记录借阅审批动作。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `application_id` | bigint unsigned | 是 | - | IDX | 借阅申请 ID |
| `approver_id` | bigint unsigned | 是 | - | IDX | 审批人 |
| `action` | varchar(16) | 是 | - | IDX | `APPROVE/REJECT` |
| `opinion` | varchar(500) | 否 | null | - | 审批意见 |
| `approved_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 审批时间 |

### 6.4.3 `borrow_checkout_record` 出库登记表

用途：记录审批通过后的实体档案借出。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `application_id` | bigint unsigned | 是 | - | UK | 借阅申请 ID |
| `archive_id` | bigint unsigned | 是 | - | IDX | 档案 ID |
| `borrower_id` | bigint unsigned | 是 | - | IDX | 领取人 |
| `operator_id` | bigint unsigned | 是 | - | IDX | 办理出库的档案员 |
| `checkout_at` | datetime | 是 | CURRENT_TIMESTAMP | IDX | 出库时间 |
| `expected_return_at` | datetime | 是 | - | IDX | 预计归还时间 |
| `location_snapshot` | varchar(255) | 否 | null | - | 借出前位置快照 |
| `checkout_note` | varchar(255) | 否 | null | - | 出库备注 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |

### 6.4.4 `borrow_return_record` 归还记录表

用途：记录归还提交、档案员验收与重新入库过程。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `application_id` | bigint unsigned | 是 | - | UK | 借阅申请 ID |
| `archive_id` | bigint unsigned | 是 | - | IDX | 档案 ID |
| `returned_by_user_id` | bigint unsigned | 是 | - | IDX | 归还提交人 |
| `received_by_user_id` | bigint unsigned | 否 | null | IDX | 验收档案员 |
| `return_status` | varchar(16) | 是 | `SUBMITTED` | IDX | 归还确认状态 |
| `handover_type` | varchar(16) | 是 | - | - | `PHOTO/DOCUMENT/BOTH` |
| `handover_note` | varchar(255) | 否 | null | - | 交接说明 |
| `returned_at` | datetime | 是 | CURRENT_TIMESTAMP | IDX | 归还提交时间 |
| `confirmed_at` | datetime | 否 | null | - | 确认入库时间 |
| `location_after_return_id` | bigint unsigned | 否 | null | IDX | 归还后位置 |
| `confirm_note` | varchar(255) | 否 | null | - | 验收备注 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |

### 6.4.5 `borrow_return_attachment` 归还附件表

用途：存储归还照片或交接单。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `return_record_id` | bigint unsigned | 是 | - | IDX | 归还记录 ID |
| `attachment_type` | varchar(16) | 是 | - | IDX | `PHOTO/HANDOVER_DOC` |
| `file_name` | varchar(255) | 是 | - | - | 文件名称 |
| `file_path` | varchar(500) | 是 | - | - | 文件路径 |
| `file_size` | bigint unsigned | 是 | 0 | - | 文件大小 |
| `uploaded_by` | bigint unsigned | 是 | - | IDX | 上传人 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |

### 6.4.6 `borrow_reminder_record` 催还记录表

用途：记录到期前、到期当天、超期后的提醒历史。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `application_id` | bigint unsigned | 是 | - | IDX | 借阅申请 ID |
| `reminder_type` | varchar(16) | 是 | - | IDX | 提醒类型 |
| `channel` | varchar(16) | 是 | - | IDX | `SITE/EMAIL` |
| `receiver_user_id` | bigint unsigned | 否 | null | IDX | 接收用户 |
| `receiver_email` | varchar(128) | 否 | null | - | 接收邮箱 |
| `send_status` | varchar(16) | 是 | `SUCCESS` | IDX | 发送状态 |
| `sent_at` | datetime | 是 | CURRENT_TIMESTAMP | IDX | 发送时间 |
| `content_summary` | varchar(255) | 否 | null | - | 内容摘要 |
| `notification_id` | bigint unsigned | 否 | null | IDX | 关联站内通知 |
| `email_task_id` | bigint unsigned | 否 | null | IDX | 关联邮件任务 |

## 6.5 销毁模块

### 6.5.1 `destroy_application` 销毁申请表

用途：记录档案销毁申请主流程。

核心约束：

1. 借出中的档案不能发起销毁。
2. 销毁原因和销毁依据必填。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `destroy_no` | varchar(64) | 是 | - | UK | 销毁单号 |
| `archive_id` | bigint unsigned | 是 | - | IDX | 档案 ID |
| `applicant_id` | bigint unsigned | 是 | - | IDX | 申请人 |
| `applicant_dept_id` | bigint unsigned | 是 | - | IDX | 申请部门 |
| `destroy_reason` | varchar(500) | 是 | - | - | 销毁原因 |
| `destroy_basis` | varchar(500) | 是 | - | - | 销毁依据 |
| `status` | varchar(32) | 是 | `PENDING_APPROVAL` | IDX | 销毁状态 |
| `approver_id` | bigint unsigned | 否 | null | IDX | 审批人 |
| `submitted_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 提交时间 |
| `approved_at` | datetime | 否 | null | - | 审批通过时间 |
| `rejected_at` | datetime | 否 | null | - | 驳回时间 |
| `reject_reason` | varchar(255) | 否 | null | - | 驳回原因 |
| `executed_at` | datetime | 否 | null | - | 实际执行时间 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |
| `updated_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 更新时间 |

### 6.5.2 `destroy_approval_record` 销毁审批记录表

用途：记录销毁审批动作。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `application_id` | bigint unsigned | 是 | - | IDX | 销毁申请 ID |
| `approver_id` | bigint unsigned | 是 | - | IDX | 审批人 |
| `action` | varchar(16) | 是 | - | IDX | `APPROVE/REJECT` |
| `opinion` | varchar(500) | 否 | null | - | 审批意见 |
| `approved_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 审批时间 |

### 6.5.3 `destroy_execution_record` 销毁执行记录表

用途：记录销毁执行留痕。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `application_id` | bigint unsigned | 是 | - | UK | 销毁申请 ID |
| `executor_id` | bigint unsigned | 是 | - | IDX | 执行人 |
| `result_status` | varchar(16) | 是 | `SUCCESS` | IDX | 执行结果 |
| `execute_note` | varchar(500) | 否 | null | - | 执行说明 |
| `executed_at` | datetime | 是 | CURRENT_TIMESTAMP | IDX | 执行时间 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |

### 6.5.4 `destroy_attachment` 销毁附件表

用途：存储销毁依据附件、执行附件等留痕文件。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `application_id` | bigint unsigned | 是 | - | IDX | 销毁申请 ID |
| `execution_record_id` | bigint unsigned | 否 | null | IDX | 销毁执行记录 ID |
| `attachment_type` | varchar(32) | 是 | - | IDX | `BASIS/EXECUTION/OTHER` |
| `file_name` | varchar(255) | 是 | - | - | 文件名称 |
| `file_path` | varchar(500) | 是 | - | - | 文件路径 |
| `file_size` | bigint unsigned | 是 | 0 | - | 文件大小 |
| `uploaded_by` | bigint unsigned | 是 | - | IDX | 上传人 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |

## 6.6 通知与审计模块

### 6.6.1 `sys_notification` 站内通知表

用途：存储站内消息。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `user_id` | bigint unsigned | 是 | - | IDX | 接收用户 |
| `notification_type` | varchar(32) | 是 | `SYSTEM` | IDX | 通知类型 |
| `title` | varchar(200) | 是 | - | - | 标题 |
| `content` | text | 是 | - | - | 通知内容 |
| `is_read` | tinyint | 是 | 0 | IDX | 是否已读 |
| `read_at` | datetime | 否 | null | - | 阅读时间 |
| `biz_type` | varchar(32) | 否 | null | IDX | 业务类型 |
| `biz_id` | bigint unsigned | 否 | null | IDX | 业务主键 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |

### 6.6.2 `sys_email_task` 邮件任务表

用途：存储邮件发送任务及结果，主要用于超期催还。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `biz_type` | varchar(32) | 是 | - | IDX | 业务类型 |
| `biz_id` | bigint unsigned | 是 | - | IDX | 业务主键 |
| `receiver_email` | varchar(128) | 是 | - | IDX | 接收邮箱 |
| `subject` | varchar(255) | 是 | - | - | 邮件主题 |
| `content` | text | 是 | - | - | 邮件内容 |
| `status` | varchar(16) | 是 | `PENDING` | IDX | `PENDING/SUCCESS/FAILED` |
| `retry_count` | int unsigned | 是 | 0 | - | 重试次数 |
| `last_error` | varchar(500) | 否 | null | - | 最后错误 |
| `sent_at` | datetime | 否 | null | - | 发送时间 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 创建时间 |
| `updated_at` | datetime | 是 | CURRENT_TIMESTAMP | - | 更新时间 |

### 6.6.3 `preview_log` 预览日志表

用途：记录在线预览行为和水印快照。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `archive_id` | bigint unsigned | 是 | - | IDX | 档案 ID |
| `file_id` | bigint unsigned | 是 | - | IDX | 档案文件 ID |
| `user_id` | bigint unsigned | 是 | - | IDX | 预览人 |
| `user_name_snapshot` | varchar(100) | 是 | - | - | 用户姓名快照 |
| `watermark_text` | varchar(255) | 是 | - | - | 水印文本 |
| `ip_address` | varchar(64) | 否 | null | - | IP 地址 |
| `user_agent` | varchar(500) | 否 | null | - | 终端信息 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | IDX | 预览时间 |

### 6.6.4 `download_log` 下载日志表

用途：记录下载确认与用途。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `archive_id` | bigint unsigned | 是 | - | IDX | 档案 ID |
| `file_id` | bigint unsigned | 是 | - | IDX | 档案文件 ID |
| `user_id` | bigint unsigned | 是 | - | IDX | 下载人 |
| `purpose` | varchar(500) | 是 | - | - | 下载用途 |
| `ip_address` | varchar(64) | 否 | null | - | IP 地址 |
| `user_agent` | varchar(500) | 否 | null | - | 终端信息 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | IDX | 下载时间 |

### 6.6.5 `audit_log` 审计日志表

用途：记录所有关键操作，满足不可修改要求。

设计要求：

1. 仅允许 `INSERT`。
2. 不提供更新和删除接口。
3. 数据库账号层面对该表禁用 `UPDATE/DELETE`。

| 字段 | 类型 | 非空 | 默认值 | 约束/索引 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `id` | bigint unsigned | 是 | 自增 | PK | 主键 |
| `module` | varchar(64) | 是 | - | IDX | 所属模块 |
| `action` | varchar(64) | 是 | - | IDX | 操作动作 |
| `target_type` | varchar(64) | 是 | - | IDX | 目标类型 |
| `target_id` | varchar(64) | 是 | - | IDX | 目标标识 |
| `operator_id` | bigint unsigned | 否 | null | IDX | 操作人 ID |
| `operator_name` | varchar(100) | 否 | null | - | 操作人姓名快照 |
| `operator_dept_id` | bigint unsigned | 否 | null | IDX | 操作人部门 |
| `request_method` | varchar(16) | 否 | null | - | 请求方法 |
| `request_path` | varchar(255) | 否 | null | - | 请求路径 |
| `ip_address` | varchar(64) | 否 | null | - | IP 地址 |
| `result` | varchar(16) | 是 | `SUCCESS` | IDX | 执行结果 |
| `detail_json` | json | 否 | null | - | 详情快照 |
| `created_at` | datetime | 是 | CURRENT_TIMESTAMP | IDX | 写入时间 |

## 7. 关键索引设计

## 7.1 唯一约束

1. `org_department.dept_code`
2. `sys_user.username`
3. `sys_role.role_code`
4. `sys_permission.permission_code`
5. `sys_user_role(user_id, role_id)`
6. `sys_role_permission(role_id, permission_id)`
7. `archive_record.archive_code`
8. `archive_storage_location.full_location_code`
9. `archive_metadata_revision(archive_id, revision_no)`
10. `scan_task.task_no`
11. `scan_task_item(task_id, archive_id)`
12. `borrow_application.application_no`
13. `borrow_checkout_record.application_id`
14. `borrow_return_record.application_id`
15. `destroy_application.destroy_no`
16. `destroy_execution_record.application_id`

## 7.2 检索与业务索引

1. `archive_record(year, security_level, status)`
2. `archive_record(responsible_dept_id, status)`
3. `archive_record(location_id, status)`
4. `borrow_application(applicant_id, status, expected_return_at)`
5. `borrow_application(current_approver_id, status)`
6. `borrow_reminder_record(application_id, reminder_type, sent_at)`
7. `destroy_application(status, approver_id, submitted_at)`
8. `sys_notification(user_id, is_read, created_at)`
9. `audit_log(module, action, created_at)`
10. `preview_log(user_id, created_at)`
11. `download_log(user_id, created_at)`

## 7.3 全文索引

建议使用 MySQL FULLTEXT：

1. `archive_record(title, keywords, summary)`
2. `archive_file(extracted_text)`

说明：

1. 全文检索以编目字段为主。
2. 电子原生 PDF 提取文本后写入 `archive_file.extracted_text`。
3. 图片扫描文件不做 OCR，因此不依赖图片正文检索。

## 8. 建表顺序建议

推荐建表顺序：

1. `org_department`
2. `sys_user`
3. `sys_role`
4. `sys_permission`
5. `sys_user_role`
6. `sys_role_permission`
7. `archive_storage_location`
8. `archive_record`
9. `archive_metadata_revision`
10. `archive_barcode`
11. `scan_task`
12. `scan_task_item`
13. `archive_file`
14. `file_process_job`
15. `borrow_application`
16. `borrow_approval_record`
17. `borrow_checkout_record`
18. `borrow_return_record`
19. `borrow_return_attachment`
20. `borrow_reminder_record`
21. `destroy_application`
22. `destroy_approval_record`
23. `destroy_execution_record`
24. `destroy_attachment`
25. `sys_notification`
26. `sys_email_task`
27. `preview_log`
28. `download_log`
29. `audit_log`

## 9. Redis 键设计

Redis 在本项目中主要承担：

1. 登录失败计数与锁定状态
2. Celery Broker / Result Backend
3. 少量短期运行状态缓存

## 9.1 登录失败计数

| Key 模板 | 类型 | TTL | 说明 |
| --- | --- | --- | --- |
| `auth:login_fail:{username}` | string | 15 分钟 | 连续失败次数 |

规则：

1. 登录失败一次，自增。
2. 达到 3 次后触发锁定。
3. 登录成功后删除该 key。

## 9.2 用户锁定状态

| Key 模板 | 类型 | TTL | 说明 |
| --- | --- | --- | --- |
| `auth:user_lock:{user_id}` | string | 15 分钟 | 用户锁定标记 |

规则：

1. 锁定时写入该 key。
2. TTL 到期自动解锁。
3. MySQL 中 `lock_until_at` 只做持久化记录。

## 9.3 Celery

| 作用 | 说明 |
| --- | --- |
| Broker | `redis://redis:6379/0` |
| Result Backend | `redis://redis:6379/1` |

说明：

1. 缩略图生成使用 Celery Worker。
2. 超期催还定时任务使用 Celery Beat。
3. 邮件发送任务使用 Celery Worker。

## 10. 数据库落地建议

## 10.1 MySQL 配置建议

1. 字符集：`utf8mb4`
2. 排序规则：`utf8mb4_unicode_ci`
3. 时区统一为 `Asia/Shanghai` 或 UTC 后应用层转换
4. 开启慢查询日志，便于优化检索与报表

## 10.2 权限建议

1. 业务库账号仅拥有本业务库访问权限。
2. 审计日志表禁止业务账号执行 `UPDATE/DELETE`。
3. 正式环境 Root 账号不用于应用连接。

## 10.3 备份建议

1. MySQL 每日全量备份。
2. Redis 开启 AOF 持久化。
3. 文件存储目录与数据库分开备份。

## 11. 结论

这份数据库设计文档已经覆盖当前项目需求对应的核心数据对象：

1. 组织与权限
2. 档案与实体位置
3. 扫描任务与文件处理
4. 借阅申请、审批、出入库、归还与催还
5. 销毁申请、审批、执行与附件
6. 通知、邮件、预览、下载、审计日志
7. Redis 登录锁定与异步任务键设计

后续如果继续落地开发，下一步最直接的工作就是根据本文档生成：

1. Django Model
2. MySQL 建表 SQL
3. 初始化角色、权限、状态枚举的基础数据
