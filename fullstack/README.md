# 岚仓档案数字化与流转系统

说明：本 README 默认以 `fullstack/` 目录作为当前工作目录。

## 当前状态

当前仓库已经完成核心业务模块开发，现阶段重点转入联调验收、异常收口、启动链路完善与文档同步。当前已交付内容包括：

1. 登录认证、失败锁定、退出登录、访问令牌刷新
2. 用户、角色、权限项、部门与审批负责人管理
3. 档案主数据、实体位置、条码二维码生成
4. 扫描任务、文件上传、缩略图与文本提取
5. 组合检索、密级脱敏、文件在线预览与下载留痕
6. 借阅申请、审批、出库、归还、催还通知
7. 销毁申请、审批、执行留痕
8. 审计日志、报表统计与 CSV 导出
9. `uv` 依赖管理、Celery 异步任务、MySQL / Redis 基础设施编排
10. 前端按需拆包、详细健康检查、日志轮转、巡检告警、备份恢复脚本
11. `docker/docker-compose.deploy.yaml` 一键部署与首次自动初始化

## 目录说明

```text
fullstack/
  backend/   后端 Django 项目
  frontend/  前端 Vue 项目
  docker/    Docker Compose 编排
  scripts/   启动、部署、测试脚本
  tests/     单元测试、API 测试、E2E 测试入口
  ops/       运维脚本
  deploy/    生产部署模板
  runtime/   运行产物目录
```

## 列表分页约定

当前项目的高频列表接口已经支持可选服务端分页，推荐在列表页、大数据场景和报表查询中统一使用：

1. 当请求参数包含 `page`、`page_size` 或 `paginate=true` 时，接口返回分页结构：

```json
{
  "code": 200,
  "message": "success",
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

2. 当未传分页参数时，接口仍保持原有数组结构，兼容既有下拉框和旧调用。
3. 当前已优先接入服务端分页的页面包括档案列表、借阅申请列表、借阅审批、借阅出库、借阅归还、销毁申请、扫描任务、通知中心、审计日志。

## 启动与部署

## 一键部署

如果你希望“不改配置文件、首次部署自动初始化、部署完成后直接登录使用”，请优先使用当前开发目录内的一键部署入口：

详细说明见 [docs/一键部署说明.md](../docs/%E4%B8%80%E9%94%AE%E9%83%A8%E7%BD%B2%E8%AF%B4%E6%98%8E.md)。

前置条件：

1. 宿主机已安装 Docker
2. 宿主机已安装 Docker Compose Plugin，即 `docker compose`
3. 宿主机已开放目标访问端口，默认是 `8080`

### 方式一：推荐脚本入口

```bash
./scripts/deploy.sh
```

执行内容包括：

1. 自动构建前端与后端镜像
2. 自动启动 MySQL、Redis、后端、Celery Worker、Celery Beat、前端 Nginx
3. 自动执行数据库迁移
4. 自动初始化基础角色、部门和示例账号
5. 自动在 `runtime/deployment_runtime/accounts.md` 输出账号清单

默认访问地址：

- 前端首页：`http://127.0.0.1:8080`
- 其他设备访问：`http://服务器IP或域名:8080`
- 后端健康检查：`http://127.0.0.1:8080/api/v1/system/health/`

初始化账号说明：

- 一键部署完成后，请以 `runtime/deployment_runtime/accounts.md` 中的实际内容为准。
- 管理员账号固定为 `admin`，密码优先使用环境变量 `ASD_ADMIN_PASSWORD`；如果未设置，部署脚本会自动生成随机密码并写入账号清单。
- 固定示例账号：
- 档案员：`archivist / Archivist12345`
- 借阅人：`borrower / Borrower12345`
- 审计员：`auditor / Auditor12345`

### 方式二：直接使用 Docker Compose

```bash
docker compose -f docker/docker-compose.deploy.yaml up -d --build
```

说明：

1. `docker/docker-compose.deploy.yaml` 已包含前端、后端、MySQL、Redis、Worker、Beat 和初始化服务
2. 首次启动会自动执行迁移与基础数据初始化
3. 账号清单同样会输出到 `runtime/deployment_runtime/accounts.md`
4. 默认关闭 `DEBUG` 与全量 CORS，并通过前端 Nginx 固定上游 Host，保证本机和常见内网访问可直接使用
5. 如果需要自定义端口、管理员密码或生产域名白名单，可在执行前设置环境变量，例如：

```bash
ASD_HTTP_PORT=8080 ASD_ADMIN_PASSWORD=MyAdmin123 DJANGO_ALLOWED_HOSTS=demo.example.com,127.0.0.1 docker compose -f docker/docker-compose.deploy.yaml up -d --build
```

### 初始化默认账号

以下账号来自 `fullstack/backend/apps/accounts/bootstrap_defaults.py`，适用于本地开发、接口联调和验收演示：

1. 管理员：`admin / 由 ASD_ADMIN_PASSWORD 指定；若未指定则首次部署自动生成`
2. 档案员：`archivist / Archivist12345`
3. 借阅人：`borrower / Borrower12345`
4. 审计员：`auditor / Auditor12345`

说明：

1. 一键部署时，最终账号密码以 `runtime/deployment_runtime/accounts.md` 为准。
2. 手工执行 `uv run manage.py bootstrap_system --username admin --password 你的安全密码` 时，管理员密码以命令参数为准，其余三个示例账号仍按上述默认值初始化。
3. 首次登录后建议立即修改所有默认密码，避免继续使用示例口令。

### 开发启动脚本

当前目录提供 `scripts/start.sh`，可直接按编号启动常用开发进程：

1. `./scripts/start.sh 1` 启动前端开发服务
2. `./scripts/start.sh 2` 启动后端开发服务
3. `./scripts/start.sh 3` 启动 Celery Worker
4. `./scripts/start.sh 4` 启动 Celery Beat

如果不带参数执行 `./scripts/start.sh`，脚本会进入交互菜单。

### 后台联动脚本

当前目录另外提供 `scripts/manage_services.sh`，用于后台管理后端联动环境：

1. `./scripts/manage_services.sh start` 启动 Redis 检查、后端服务、Celery Worker、Celery Beat
2. `./scripts/manage_services.sh status` 查看当前是“脚本管理中”还是“外部已运行”
3. `./scripts/manage_services.sh logs worker` 查看指定服务最近日志
4. `./scripts/manage_services.sh stop` 停止脚本自己拉起的服务
5. `./scripts/manage_services.sh restart` 重启脚本管理的后台链路

说明：

- `manage_services.sh` 不会停止外部手工启动的服务，只会停止它自己记录了 PID 的进程。
- 如果 `127.0.0.1:6379` 上没有 Redis，脚本会尝试通过 `docker/docker-compose.yaml` 拉起 Redis 容器。
- 运行期日志和 PID 会写入 `runtime/services/`。
- 详细运维说明见 [docs/异步任务与运维启动说明.md](../docs/%E5%BC%82%E6%AD%A5%E4%BB%BB%E5%8A%A1%E4%B8%8E%E8%BF%90%E7%BB%B4%E5%90%AF%E5%8A%A8%E8%AF%B4%E6%98%8E.md)。

### 运维脚本

当前目录提供 `ops/` 运维脚本目录：

1. `./ops/rotate_runtime_logs.sh`：轮转 `runtime/services/logs/` 与 `backend/logs/`
2. `./ops/monitor_services.sh`：巡检后端详细健康、Redis、Worker、Beat，并支持真实 Webhook / SMTP 邮件告警
3. `./ops/backup_system.sh`：备份数据库、媒体文件和 `.env`
4. `./ops/restore_system.sh`：按备份目录恢复数据库和媒体文件

详细说明见 [docs/日志监控与备份恢复说明.md](../docs/%E6%97%A5%E5%BF%97%E7%9B%91%E6%8E%A7%E4%B8%8E%E5%A4%87%E4%BB%BD%E6%81%A2%E5%A4%8D%E8%AF%B4%E6%98%8E.md)。

### 生产部署模板

当前目录提供 `deploy/` 目录，已经提供以下模板：

1. `deploy/systemd/`：Gunicorn、Celery Worker、Celery Beat 的 `systemd` 服务模板
2. `deploy/supervisor/`：Supervisor 进程守护模板
3. `deploy/nginx/`：Nginx + HTTPS 反向代理模板
4. `deploy/env/`：生产环境变量示例
5. `deploy/logrotate/`：日志轮转模板

部署步骤与字段说明见 [docs/生产部署模板说明.md](../docs/%E7%94%9F%E4%BA%A7%E9%83%A8%E7%BD%B2%E6%A8%A1%E6%9D%BF%E8%AF%B4%E6%98%8E.md)。

### 后端

1. 进入目录：`cd backend`
2. 复制环境变量：`cp .env.example .env`
3. 同步基础依赖：`uv sync`
4. 执行数据库迁移：`uv run manage.py migrate`
5. 初始化基础账号：`uv run manage.py bootstrap_system --username admin --password 请替换为安全密码`
6. 本地开发启动：`uv run manage.py runserver 0.0.0.0:8000`
7. 启动 Celery Worker：`uv run celery -A config.celery:app worker --loglevel=info`
8. 启动 Celery Beat：`uv run celery -A config.celery:app beat --loglevel=info`

说明：

- 默认使用 SQLite 作为本地兜底数据库。
- 如果需要接入 MySQL，请先执行 `uv sync --extra mysql`，再在 `.env` 中将 `DB_ENGINE` 改为 `mysql`，并补齐 `DB_HOST`、`DB_PORT`、`DB_NAME`、`DB_USER`、`DB_PASSWORD`。
- 首次启动建议先执行 `bootstrap_system` 命令生成根部门、基础角色、各角色示例账号，并输出到 `runtime/deployment_runtime/accounts.md`。
- 如果需要运行催还扫描、邮件发送、缩略图生成等异步链路，请同时启动 Redis、Celery Worker 和 Celery Beat。
- 如果需要验证真实外部邮件 / Webhook 链路，可执行：

```bash
uv run manage.py verify_notification_channels --email ops@example.com
uv run manage.py verify_notification_channels --webhook https://example.com/webhook
uv run manage.py verify_notification_channels --email ops@example.com --webhook https://example.com/webhook --webhook-header "Authorization: Bearer token"
```

- 若邮件服务使用 465 端口，请在 `.env` 中配置 `EMAIL_USE_SSL=true`；若使用 587 STARTTLS，请配置 `EMAIL_USE_TLS=true` 且 `EMAIL_USE_SSL=false`。

后端目录当前采用 DRF 常见分层组织：

```text
backend/
  config/
  apps/
    system/
      api/
      services.py
      tests/
```

### 前端

1. 进入目录：`cd frontend`
2. 安装依赖：`npm install`
3. 复制环境变量：`cp .env.example .env`
4. 启动开发服务：`npm run dev`

默认访问地址：

- 前端开发服务：`http://127.0.0.1:5173`
- 后端开发服务：`http://127.0.0.1:8000`
- 后端健康检查：`http://127.0.0.1:8000/api/v1/system/health/`
- 后端详细健康检查：`http://127.0.0.1:8000/api/v1/system/health/detail/`（仅管理员或内网请求可访问）

## 基础设施启动

1. 进入目录：`cd docker`
2. 启动基础设施：`docker compose up -d`

默认访问地址：

- MySQL：`127.0.0.1:3306`
- Redis：`127.0.0.1:6379`

## 当前验证方式

- 后端静态检查：`cd backend && uv run manage.py check`
- 前端类型校验：`cd frontend && npm run type-check`
- 分页与通知链路定向测试：`cd backend && uv run manage.py test apps.archives.tests.test_archive_api apps.audit.tests.test_audit_api apps.borrowing.tests.test_borrowing_api apps.notifications.tests.test_notification_api apps.notifications.tests.test_notification_command`
- 单元测试：`./scripts/run_tests.sh unit`
- API 接口测试：`./scripts/run_tests.sh api`
- 前端 E2E 联调测试：`./scripts/run_tests.sh e2e`
- 验收总回归：`./scripts/run_tests.sh full`

## 当前待完善重点

1. 在正式企业 SMTP / Webhook 地址上完成一次实网演练并固化告警参数
2. 结合正式生产环境收紧默认密码、域名白名单、HTTPS 与防火墙策略
