from unittest.mock import patch

from django.test import SimpleTestCase

from apps.system.services import build_health_detail_payload


class SystemServicesUnitTests(SimpleTestCase):
    @patch(
        "apps.system.services.check_storage_health",
        return_value={"status": "warning", "message": "磁盘空间不足。", "usage_percent": 88.0},
    )
    @patch(
        "apps.system.services.check_redis_health",
        return_value={"status": "ok", "message": "Redis 正常。", "latency_ms": 3.2},
    )
    @patch(
        "apps.system.services.check_database_health",
        return_value={"status": "ok", "message": "数据库正常。", "latency_ms": 1.1},
    )
    def test_build_health_detail_payload_should_mark_warning_when_any_check_warns(self, *_args) -> None:
        payload = build_health_detail_payload()

        self.assertEqual(payload["status"], "warning")
        self.assertEqual(payload["checks"]["storage"]["status"], "warning")

    @patch(
        "apps.system.services.check_storage_health",
        return_value={"status": "ok", "message": "磁盘正常。", "usage_percent": 35.0},
    )
    @patch(
        "apps.system.services.check_redis_health",
        return_value={"status": "error", "message": "Redis 连接失败。"},
    )
    @patch(
        "apps.system.services.check_database_health",
        return_value={"status": "ok", "message": "数据库正常。", "latency_ms": 1.1},
    )
    def test_build_health_detail_payload_should_mark_error_when_any_check_fails(self, *_args) -> None:
        payload = build_health_detail_payload()

        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["checks"]["redis"]["status"], "error")
