from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from apps.audit.models import AuditLog
from apps.accounts.models import DataScope, Role
from apps.accounts.services import assign_roles_to_user
from apps.notifications.models import NotificationType, SystemNotification
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class AuthApiTests(APITestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.root_department = Department.objects.create(
            dept_code="ROOT",
            dept_name="总部",
        )
        sync_department_hierarchy(self.root_department)

        self.admin_role = Role.objects.create(
            role_code="ADMIN",
            role_name="管理员",
            data_scope=DataScope.ALL,
        )
        self.user_role = Role.objects.create(
            role_code="BORROWER",
            role_name="借阅人",
            data_scope=DataScope.SELF,
        )

        self.admin_user = User.objects.create_user(
            username="admin",
            password="Admin12345",
            real_name="系统管理员",
            dept=self.root_department,
            is_staff=True,
        )
        assign_roles_to_user(self.admin_user, [self.admin_role.id])

        self.normal_user = User.objects.create_user(
            username="reader",
            password="Reader12345",
            real_name="普通用户",
            dept=self.root_department,
        )
        assign_roles_to_user(self.normal_user, [self.user_role.id])

    def test_login_success_should_return_tokens_and_profile(self) -> None:
        response = self.client.post(
            "/api/v1/auth/login/",
            {
                "username": "reader",
                "password": "Reader12345",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json()["data"]["tokens"])
        self.assertEqual(response.json()["data"]["profile"]["username"], "reader")
        self.assertTrue(
            AuditLog.objects.filter(action_code="LOGIN_SUCCESS", username="reader").exists()
        )

    def test_login_should_lock_user_after_three_failures_and_admin_can_unlock(self) -> None:
        for index in range(3):
            response = self.client.post(
                "/api/v1/auth/login/",
                {
                    "username": "reader",
                    "password": "wrong-password",
                },
                format="json",
            )

            if index < 2:
                self.assertEqual(response.status_code, 400)
            else:
                self.assertEqual(response.status_code, 423)

        self.normal_user.refresh_from_db()
        self.assertEqual(self.normal_user.failed_login_count, 3)
        self.assertIsNotNone(self.normal_user.lock_until_at)

        self.client.force_authenticate(self.admin_user)
        unlock_response = self.client.post(f"/api/v1/auth/unlock/{self.normal_user.id}/")

        self.assertEqual(unlock_response.status_code, 200)

        self.normal_user.refresh_from_db()
        self.assertEqual(self.normal_user.failed_login_count, 0)
        self.assertIsNone(self.normal_user.lock_until_at)
        self.assertGreaterEqual(
            AuditLog.objects.filter(username="reader", action_code__in=["LOGIN_FAILED", "LOGIN_LOCKED"]).count(),
            3,
        )
        self.assertTrue(AuditLog.objects.filter(action_code="USER_UNLOCK", username="admin").exists())
        unlock_notification = SystemNotification.objects.filter(
            user=self.normal_user,
            notification_type=NotificationType.SYSTEM,
            title="账号已解锁",
        ).first()
        self.assertIsNotNone(unlock_notification)
        self.assertIsNone(unlock_notification.biz_type)
        self.assertIn("已为你解除登录锁定", unlock_notification.content)

    def test_logout_should_record_audit_log(self) -> None:
        self.client.force_authenticate(self.normal_user)

        response = self.client.post("/api/v1/auth/logout/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "退出成功")
        self.assertTrue(AuditLog.objects.filter(action_code="LOGOUT", username="reader").exists())

    def test_refresh_token_should_issue_new_access_token_and_record_audit_log(self) -> None:
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {
                "username": "reader",
                "password": "Reader12345",
            },
            format="json",
        )

        refresh_token = login_response.json()["data"]["tokens"]["refresh"]
        response = self.client.post(
            "/api/v1/auth/refresh/",
            {
                "refresh": refresh_token,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json()["data"])
        self.assertTrue(AuditLog.objects.filter(action_code="TOKEN_REFRESH", username="reader").exists())

    def test_refresh_token_should_reject_invalid_token(self) -> None:
        response = self.client.post(
            "/api/v1/auth/refresh/",
            {
                "refresh": "invalid-refresh-token",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["message"], "刷新令牌无效或已过期。")
        self.assertTrue(AuditLog.objects.filter(action_code="TOKEN_REFRESH_FAILED").exists())
