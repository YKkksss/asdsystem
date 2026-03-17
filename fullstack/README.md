# 岚仓档案数字化与流转系统

说明：本 README 默认以 `fullstack/` 目录作为当前工作目录。

## 当前状态

当前仓库已经完成核心业务模块开发，现阶段重点转入联调验收、异常收口、启动链路完善与文档同步。当前已交付内容包括：

1. 登录认证、失败锁定、退出登录、访问令牌刷新
2. 用户、角色、权限项、部门与审批负责人管理
3. 档案主数据、实体位置、条码二维码生成
4. 扫描任务、文件上传、缩略图与文本提取
5. 组合检索、密级脱敏、文件在线预览与下载留痕
6. 借阅申请、审批、出库、归还、催还通知与通知链路脱敏
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

## 启动与部署

## 一键部署

如果你希望“不改配置文件、首次部署自动初始化、部署完成后直接登录使用”，请优先使用当前开发目录内的一键部署入口：

详细说明见 [docs/one-click-deployment.md](../docs/one-click-deployment.md)。

前置条件：

1. 宿主机已安装 Docker
2. 宿主机已安装 Docker Compose Plugin，即 `docker compose`
3. 宿主机已开放目标访问端口，默认是 `8080`

### 方式一：部署脚本一键启动(推荐)

```bash
./scripts/deploy.sh
```
本脚本基于docker compose启动
执行内容包括：
1. 自动判断前后端源码或镜像是否变化，仅在首次部署、镜像缺失或源码发生变化时重新构建对应镜像
2. 自动启动 MySQL、Redis、后端、Celery Worker、Celery Beat、前端 Nginx
3. 自动执行数据库迁移
4. 自动检查基础角色、部门、权限和默认账号是否缺失，仅在首次部署或基础数据不完整时执行基础初始化
5. 重复部署默认保留已有账号密码，不再自动重置为默认口令
6. 自动在 `runtime/deployment_runtime/accounts.md` 输出账号清单

说明：

1. 当前部署脚本只负责基础账号、角色、权限和部门初始化，不再在部署过程中自动写入演示业务数据。
2. 如果数据库卷被清空、基础账号被删除、权限项缺失，部署脚本会在启动时自动补齐基础数据。
3. 如果只是二次更新且镜像、源码和基础数据都没有变化，则脚本会直接复用现有镜像和已有基础数据。
4. 如需补充演示或验收数据，请在部署完成后单独执行 `./scripts/init_demo_data.sh`。
5. 如需强制重新构建本地镜像，可在执行前临时附加 `ASD_FORCE_BUILD=true`。

默认访问地址：

- 前端首页：`http://127.0.0.1:8080`
- 其他设备访问：`http://服务器IP或域名:8080`
- 后端健康检查：`http://127.0.0.1:8080/api/v1/system/health/`

初始化账号说明：

- 一键部署完成后，请以 `runtime/deployment_runtime/accounts.md` 中的实际内容为准。
- 管理员账号固定为 `admin`，密码优先使用环境变量 `ASD_ADMIN_PASSWORD`；如果未设置，则默认初始化为 `Admin12345`。
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
5. Docker 前端容器会直接提供 `/media/` 与 `/static/`，条码、二维码、缩略图和后台静态资源不再依赖 Django `DEBUG=true`
6. `backend-init` 会在容器内自动判断基础系统数据是否缺失；如果数据库已完整初始化，则只执行迁移和静态资源同步，不重复重置默认账号密码
7. 如果需要补充演示业务数据，请在部署完成后单独执行 `./scripts/init_demo_data.sh`
8. 如果需要自定义端口、管理员密码或生产域名白名单，可在执行前设置环境变量，例如：

```bash
ASD_HTTP_PORT=8080 ASD_ADMIN_PASSWORD=MyAdmin123 DJANGO_ALLOWED_HOSTS=demo.example.com,127.0.0.1 docker compose -f docker/docker-compose.deploy.yaml up -d --build
```

### 示例/测试数据初始化

如需补充档案、借阅、销毁、通知等演示业务数据，请在基础部署完成后执行：

```bash
./scripts/init_demo_data.sh
```

可选：

1. `./scripts/init_demo_data.sh docker`：在 Docker 部署环境中执行，适合一键部署后的初始化。
2. `./scripts/init_demo_data.sh local`：在本地 `uv` 后端环境中执行。

说明：

1. 该脚本底层调用 `bootstrap_demo_data`，可重复执行，不会无限重复堆积同一批示例数据。
2. 执行前请确保基础账号已经初始化完成。

### 初始化默认账号

以下账号来自 `fullstack/backend/apps/accounts/bootstrap_defaults.py`，适用于本地开发、接口联调和验收演示：

1. 管理员：`admin / Admin12345`
2. 档案员：`archivist / Archivist12345`
3. 借阅人：`borrower / Borrower12345`
4. 审计员：`auditor / Auditor12345`

说明：

1. 一键部署时，最终账号密码以 `runtime/deployment_runtime/accounts.md` 为准。
2. 手工执行 `uv run manage.py bootstrap_system --username admin --password 你的安全密码` 时，管理员密码以命令参数为准；如果通过 Docker 一键部署且未显式设置 `ASD_ADMIN_PASSWORD`，则会回退为 `Admin12345`。
3. 首次登录后建议立即修改所有默认密码，避免继续使用示例口令。
4. 当前内置角色的默认菜单职责如下：
   - 管理员：拥有全部菜单、按钮与系统配置权限。
   - 档案员：默认可见工作台、档案业务、借阅业务、通知中心与报表中心，不默认承担借阅审批与审计日志查看。
   - 借阅人：默认只保留工作台、借阅中心、归还中心、通知中心等个人借阅相关入口。
   - 审计员：默认聚焦工作台、通知中心、报表中心、审计日志等监督类只读入口，不默认进入档案中心和销毁中心。

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
- 详细运维说明见 [docs/async-tasks-and-ops-startup.md](../docs/async-tasks-and-ops-startup.md)。

### 运维脚本

当前目录提供 `ops/` 运维脚本目录：

1. `./ops/rotate_runtime_logs.sh`：轮转 `runtime/services/logs/` 与 `backend/logs/`
2. `./ops/monitor_services.sh`：巡检后端详细健康、Redis、Worker、Beat，并支持真实 Webhook / SMTP 邮件告警
3. `./ops/backup_system.sh`：备份数据库、媒体文件和 `.env`
4. `./ops/restore_system.sh`：按备份目录恢复数据库和媒体文件

详细说明见 [docs/logging-monitoring-backup-restore.md](../docs/logging-monitoring-backup-restore.md)。

### 生产部署模板

当前目录提供 `deploy/` 目录，已经提供以下模板：

1. `deploy/systemd/`：Gunicorn、Celery Worker、Celery Beat 的 `systemd` 服务模板
2. `deploy/supervisor/`：Supervisor 进程守护模板
3. `deploy/nginx/`：Nginx + HTTPS 反向代理模板
4. `deploy/env/`：生产环境变量示例
5. `deploy/logrotate/`：日志轮转模板

部署步骤与字段说明见 [docs/production-deployment-template-guide.md](../docs/production-deployment-template-guide.md)。

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
- 如需补充演示验收数据，可在基础账号初始化完成后执行 `./scripts/init_demo_data.sh local`，或直接执行 `uv run manage.py bootstrap_demo_data`。
- 如果需要运行催还扫描、邮件发送、缩略图生成等异步链路，请同时启动 Redis、Celery Worker 和 Celery Beat。
- 如果需要验证真实外部邮件 / Webhook 链路，可执行：

```bash
uv run manage.py verify_notification_channels --email ops@example.com
uv run manage.py verify_notification_channels --webhook https://example.com/webhook
uv run manage.py verify_notification_channels --email ops@example.com --webhook https://example.com/webhook --webhook-header "Authorization: Bearer token"
```

- 上述命令在终端中的 `webhook` 字段会自动脱敏，便于保留排障线索同时避免泄露真实回调地址。
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
- 默认仅监听本机回环地址 `127.0.0.1:5173`
- 不再提供前端开发服务的公网 IP / 域名直连方式
- 如需一键启动本地前端，可在 `fullstack/` 目录执行：`./scripts/start.sh 1`

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
- 工作台与角色视角定向测试：`cd backend && uv run manage.py test apps.system.tests.test_dashboard_api`
- 分页与通知链路定向测试：`cd backend && uv run manage.py test apps.archives.tests.test_archive_api apps.audit.tests.test_audit_api apps.borrowing.tests.test_borrowing_api apps.notifications.tests.test_notification_api apps.notifications.tests.test_notification_command`
- 通知脱敏定向测试：`cd backend && uv run manage.py test apps.notifications.tests.test_notification_services_unit apps.notifications.tests.test_notification_command`
- 文件访问权限正负向回归：`cd frontend && npx playwright test tests/e2e/archive-file-access.spec.ts tests/e2e/archive-file-access-restricted.spec.ts`
- 内置角色菜单与直链拦截回归：`cd frontend && npx playwright test tests/e2e/auth-and-permission.spec.ts`
- 通知深链与业务直达回归：`cd frontend && npx playwright test tests/e2e/notification-deeplink.spec.ts`
- 单元测试：`./scripts/run_tests.sh unit`
- API 接口测试：`./scripts/run_tests.sh api`
- 前端 E2E 联调测试：`./scripts/run_tests.sh e2e`
- 验收总回归：`./scripts/run_tests.sh full`

## 当前待完善重点

1. 在正式企业 SMTP / Webhook 地址上完成一次实网演练并固化告警参数
2. 结合正式生产环境收紧默认密码、域名白名单、HTTPS 与防火墙策略
