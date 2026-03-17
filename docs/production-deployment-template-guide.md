# 生产部署模板说明

## 适用目标

本文档用于说明当前项目新增的生产部署模板如何落地，包括：

1. `systemd` 进程守护模板
2. `supervisor` 进程守护模板
3. `Nginx + HTTPS` 反向代理模板
4. 生产环境变量示例
5. 日志轮转模板

本模板面向以下部署形态：

1. 前端构建产物由 Nginx 直接托管
2. Django 后端通过 Gunicorn 提供 WSGI 服务
3. Redis 作为 Celery Broker / Result Backend
4. Celery Worker 与 Celery Beat 独立运行
5. 生产日志通过 logrotate 统一轮转

## 模板目录

新增模板位于仓库中的 `fullstack/deploy/`：

```text
fullstack/deploy/
  env/
    backend.production.env.example
  logrotate/
    asd-system.conf
  nginx/
    asd-system.conf.example
  supervisor/
    asd-system.conf
  systemd/
    asd-backend.service
    asd-celery-worker.service
    asd-celery-beat.service
```

## 依赖准备

后端生产模板使用 Gunicorn，因此后端 `uv` 依赖已经新增 `deploy` 可选依赖组。

如果你使用 SQLite 演示环境：

```bash
cd fullstack/backend
uv sync --extra deploy
```

如果你使用 MySQL 生产环境：

```bash
cd fullstack/backend
uv sync --extra mysql --extra deploy
```

同步完成后，应能看到：

1. `fullstack/backend/.venv/bin/gunicorn`
2. `fullstack/backend/.venv/bin/celery`

## 前端构建与后端静态资源

上线前建议执行：

```bash
cd /srv/asd-system/fullstack/frontend
npm install
npm run build

cd /srv/asd-system/fullstack/backend
uv run manage.py migrate
uv run manage.py collectstatic --noinput
```

说明：

1. 前端构建产物默认输出到 `fullstack/frontend/dist`
2. Django 静态资源默认输出到 `fullstack/backend/staticfiles`
3. 媒体文件目录默认位于 `fullstack/backend/media`

## 环境变量模板

请先复制环境变量模板：

```bash
mkdir -p /srv/asd-system/fullstack/deploy/env
cp fullstack/deploy/env/backend.production.env.example /srv/asd-system/fullstack/deploy/env/backend.production.env
```

至少需要按实际环境修改以下字段：

1. `DJANGO_SECRET_KEY`
2. `DJANGO_ALLOWED_HOSTS`
3. `DJANGO_CORS_ALLOWED_ORIGINS`
4. `DB_*`
5. `EMAIL_*`

## systemd 部署方式

### 1. 拷贝服务模板

```bash
sudo cp fullstack/deploy/systemd/asd-backend.service /etc/systemd/system/
sudo cp fullstack/deploy/systemd/asd-celery-worker.service /etc/systemd/system/
sudo cp fullstack/deploy/systemd/asd-celery-beat.service /etc/systemd/system/
```

### 2. 根据实际路径修改模板

请重点核对以下字段：

1. `User`
2. `Group`
3. `WorkingDirectory`
4. `EnvironmentFile`
5. `ExecStart`

如果你的部署路径不是 `/srv/asd-system`，必须整体替换。

### 3. 重新加载并启动

```bash
sudo systemctl daemon-reload
sudo systemctl enable asd-backend asd-celery-worker asd-celery-beat
sudo systemctl start asd-backend
sudo systemctl start asd-celery-worker
sudo systemctl start asd-celery-beat
```

### 4. 查看状态与日志

```bash
sudo systemctl status asd-backend
sudo systemctl status asd-celery-worker
sudo systemctl status asd-celery-beat

sudo journalctl -u asd-backend -f
sudo journalctl -u asd-celery-worker -f
sudo journalctl -u asd-celery-beat -f
```

## supervisor 部署方式

### 1. 拷贝模板

```bash
sudo mkdir -p /etc/supervisor/conf.d
sudo cp fullstack/deploy/supervisor/asd-system.conf /etc/supervisor/conf.d/
```

### 2. 修改模板中的路径

需要按实际机器调整：

1. `directory`
2. `command`
3. `user`
4. `stdout_logfile`
5. `stderr_logfile`

### 3. 创建日志目录

```bash
sudo mkdir -p /var/log/asd-system
sudo chown -R www-data:www-data /var/log/asd-system
```

### 4. 重新加载配置

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status
```

## Nginx 部署方式

模板文件位于：

`fullstack/deploy/nginx/asd-system.conf.example`

### 1. 修改域名与证书路径

请重点替换：

1. `server_name`
2. `ssl_certificate`
3. `ssl_certificate_key`
4. `root`
5. `alias`
6. 代理目标 `127.0.0.1:8000`

### 2. 安装配置

```bash
sudo cp fullstack/deploy/nginx/asd-system.conf.example /etc/nginx/conf.d/asd-system.conf
sudo nginx -t
sudo systemctl reload nginx
```

### 3. 当前模板职责

Nginx 模板已经覆盖：

1. `80 -> 443` 跳转
2. 前端静态资源托管
3. Vue 静态路由回退到 `index.html`
4. `/api/`、`/admin/` 反向代理
5. `/media/`、`/static/` 静态目录暴露

## 日志轮转模板

模板文件位于：

`fullstack/deploy/logrotate/asd-system.conf`

使用示例：

```bash
sudo cp fullstack/deploy/logrotate/asd-system.conf /etc/logrotate.d/asd-system
sudo logrotate -d /etc/logrotate.d/asd-system
```

当前模板默认覆盖：

1. `/var/log/asd-system/*.log`
2. `/srv/asd-system/fullstack/backend/logs/*.log`

如果你的部署路径不是 `/srv/asd-system`，请同步修改模板中的路径。

## 推荐部署顺序

建议按以下顺序落地：

1. 准备代码目录，例如 `/srv/asd-system`
2. 同步后端依赖：`uv sync --extra mysql --extra deploy`
3. 构建前端：`npm run build`
4. 执行迁移与静态资源收集
5. 配置 `backend.production.env`
6. 启动 Redis / MySQL
7. 启动 Gunicorn
8. 启动 Celery Worker / Beat
9. 配置并重载 Nginx

## 上线后验证

上线完成后建议至少执行以下检查：

```bash
curl http://127.0.0.1:8000/api/v1/system/health/
curl -I https://archive.example.com
```

还应检查：

1. 首页是否正常加载
2. 登录是否成功
3. `/api/v1/system/health/` 是否返回成功
4. Worker 是否已连接 Redis
5. Beat 是否已正常启动

## 当前模板边界

本次提供的是“可直接修改并落地的生产模板”，但还没有覆盖以下高级运维项：

1. `systemd` 的资源限制与 CPU / 内存隔离
2. Nginx 的更细粒度安全头配置
3. 企业微信、钉钉等特定告警通道适配
4. 备份异地复制与定期恢复演练自动化

这些将作为后续工程化优化继续补齐。
