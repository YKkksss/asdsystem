from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import DataScope, Role
from apps.accounts.services import assign_roles_to_user
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class HealthApiTests(TestCase):
    def setUp(self) -> None:
        self.department = Department.objects.create(
            dept_code="OPS",
            dept_name="运维部",
        )
        sync_department_hierarchy(self.department)
        self.admin_role = Role.objects.create(
            role_code="ADMIN",
            role_name="管理员",
            data_scope=DataScope.ALL,
            status=True,
        )
        self.admin_user = User.objects.create_user(
            username="health_admin",
            password="HealthAdmin12345",
            real_name="健康检查管理员",
            dept=self.department,
            is_staff=True,
        )
        assign_roles_to_user(self.admin_user, [self.admin_role.id])

    def test_root_health_returns_success(self) -> None:
        response = self.client.get(reverse("root-health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["code"], 200)

    def test_api_health_returns_success(self) -> None:
        response = self.client.get("/api/v1/system/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["service"], "backend")

    def test_api_health_detail_returns_dependency_checks(self) -> None:
        response = self.client.get("/api/v1/system/health/detail/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["checks"]["database"]["status"], "ok")
        self.assertIn(response.json()["data"]["checks"]["redis"]["status"], {"ok", "error"})
        self.assertIn("usage_percent", response.json()["data"]["checks"]["storage"])
        self.assertNotIn("environment", response.json()["data"])
        self.assertNotIn("path", response.json()["data"]["checks"]["storage"])

    def test_api_health_detail_should_reject_public_anonymous_request(self) -> None:
        response = self.client.get(
            "/api/v1/system/health/detail/",
            HTTP_X_FORWARDED_FOR="8.8.8.8",
            REMOTE_ADDR="8.8.8.8",
        )

        self.assertEqual(response.status_code, 401)

    def test_api_health_detail_should_allow_admin_request_from_public_network(self) -> None:
        self.client.force_login(self.admin_user)

        response = self.client.get(
            "/api/v1/system/health/detail/",
            HTTP_X_FORWARDED_FOR="8.8.8.8",
            REMOTE_ADDR="8.8.8.8",
        )

        self.assertEqual(response.status_code, 200)
