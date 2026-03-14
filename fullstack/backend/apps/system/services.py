import shutil
from time import perf_counter
from typing import Any

from django.conf import settings
from django.db import connections
from django.db.utils import DatabaseError
from django.utils import timezone
from redis import Redis
from redis.exceptions import RedisError


HEALTH_VERSION = "0.1.0"


def build_health_payload(*, include_message: bool) -> dict[str, str]:
    payload = _build_base_payload(status="ok")

    if include_message:
        payload["message"] = "岚仓档案数字化与流转系统后端已启动"

    return payload


def build_health_detail_payload() -> dict[str, Any]:
    checks = {
        "database": check_database_health(),
        "redis": check_redis_health(),
        "storage": check_storage_health(),
    }

    payload = _build_base_payload(status=resolve_health_status(checks))
    payload["checks"] = checks
    payload["environment"] = {
        "debug": settings.DEBUG,
        "db_engine": settings.DB_ENGINE,
    }
    return payload


def check_database_health() -> dict[str, Any]:
    started_at = perf_counter()

    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError as exc:
        return {
            "status": "error",
            "message": f"数据库连接异常：{exc}",
        }

    return {
        "status": "ok",
        "message": "数据库连接正常。",
        "latency_ms": round((perf_counter() - started_at) * 1000, 2),
    }


def check_redis_health() -> dict[str, Any]:
    started_at = perf_counter()

    try:
        client = Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
    except (RedisError, ValueError) as exc:
        return {
            "status": "error",
            "message": f"Redis 连接异常：{exc}",
        }

    return {
        "status": "ok",
        "message": "Redis 连接正常。",
        "latency_ms": round((perf_counter() - started_at) * 1000, 2),
    }


def check_storage_health() -> dict[str, Any]:
    media_path = settings.MEDIA_ROOT
    usage_target = media_path if media_path.exists() else media_path.parent
    total, used, free = shutil.disk_usage(usage_target)
    usage_percent = round((used / total) * 100, 2) if total else 0.0

    if usage_percent >= settings.SYSTEM_STORAGE_CRITICAL_PERCENT:
        status = "error"
        message = f"媒体目录所在磁盘使用率过高，当前为 {usage_percent}%。"
    elif usage_percent >= settings.SYSTEM_STORAGE_WARNING_PERCENT:
        status = "warning"
        message = f"媒体目录所在磁盘使用率接近阈值，当前为 {usage_percent}%。"
    else:
        status = "ok"
        message = "媒体目录所在磁盘容量充足。"

    return {
        "status": status,
        "message": message,
        "path": str(usage_target),
        "usage_percent": usage_percent,
        "free_gb": round(free / (1024 ** 3), 2),
    }


def resolve_health_status(checks: dict[str, dict[str, Any]]) -> str:
    statuses = {check["status"] for check in checks.values()}
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    return "ok"


def _build_base_payload(*, status: str) -> dict[str, str]:
    return {
        "service": "backend",
        "status": status,
        "time": timezone.now().isoformat(),
        "version": HEALTH_VERSION,
    }
