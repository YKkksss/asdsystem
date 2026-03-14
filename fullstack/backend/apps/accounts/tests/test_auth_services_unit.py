from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import SecurityClearance
from apps.accounts.services import get_locked_until, refresh_access_token, register_login_failure
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class AuthServicesUnitTests(TestCase):
    def setUp(self) -> None:
        cache.clear()
        self.department = Department.objects.create(
            dept_code="UNIT_AUTH",
            dept_name="认证单元测试部",
        )
        sync_department_hierarchy(self.department)

        self.user = User.objects.create_user(
            username="unit_auth_user",
            password="UnitAuth12345",
            real_name="认证单元测试用户",
            dept=self.department,
            security_clearance_level=SecurityClearance.INTERNAL,
            status=True,
        )

    def tearDown(self) -> None:
        cache.clear()
        super().tearDown()

    def test_register_login_failure_should_lock_user_after_limit(self) -> None:
        first_fail_count, first_lock_until = register_login_failure(self.user)
        second_fail_count, second_lock_until = register_login_failure(self.user)
        third_fail_count, third_lock_until = register_login_failure(self.user)

        self.user.refresh_from_db()

        self.assertEqual(first_fail_count, 1)
        self.assertIsNone(first_lock_until)
        self.assertEqual(second_fail_count, 2)
        self.assertIsNone(second_lock_until)
        self.assertEqual(third_fail_count, 3)
        self.assertIsNotNone(third_lock_until)
        self.assertEqual(self.user.failed_login_count, 3)
        self.assertIsNotNone(self.user.lock_until_at)
        self.assertIsNotNone(get_locked_until(self.user))

    def test_get_locked_until_should_read_cached_value_first(self) -> None:
        lock_until = timezone.now() + timedelta(minutes=5)
        cache.set(f"auth:user_lock:{self.user.id}", lock_until.isoformat(), timeout=300)

        resolved_lock_until = get_locked_until(self.user)

        self.assertIsNotNone(resolved_lock_until)
        self.assertEqual(resolved_lock_until.isoformat(), lock_until.isoformat())

    def test_refresh_access_token_should_reject_disabled_user(self) -> None:
        refresh_token = str(RefreshToken.for_user(self.user))
        self.user.status = False
        self.user.save(update_fields=["status", "updated_at"])

        with self.assertRaisesMessage(PermissionDenied, "当前账号已停用，请重新登录。"):
            refresh_access_token(refresh_token)
