from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import Role, SystemPermission, UserRole
from apps.organizations.models import Department


User = get_user_model()


class BootstrapSystemCommandTests(TestCase):
    def test_bootstrap_system_should_create_departments_roles_users_and_account_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            account_file = Path(temp_dir) / "accounts.md"

            call_command(
                "bootstrap_system",
                username="admin",
                password="Admin12345",
                real_name="系统管理员",
                account_file=str(account_file),
            )
            call_command(
                "bootstrap_system",
                username="admin",
                password="Admin12345",
                real_name="系统管理员",
                account_file=str(account_file),
            )

            self.assertEqual(Role.objects.count(), 4)
            self.assertGreaterEqual(SystemPermission.objects.count(), 10)
            self.assertEqual(Department.objects.count(), 4)
            self.assertEqual(User.objects.filter(username__in=["admin", "archivist", "borrower", "auditor"]).count(), 4)

            admin_user = User.objects.get(username="admin")
            archivist_user = User.objects.get(username="archivist")
            borrower_user = User.objects.get(username="borrower")
            auditor_user = User.objects.get(username="auditor")

            self.assertTrue(admin_user.check_password("Admin12345"))
            self.assertTrue(archivist_user.check_password("Archivist12345"))
            self.assertTrue(borrower_user.check_password("Borrower12345"))
            self.assertTrue(auditor_user.check_password("Auditor12345"))

            self.assertEqual(UserRole.objects.filter(user=admin_user).count(), 1)
            self.assertEqual(UserRole.objects.filter(user=archivist_user).count(), 1)
            self.assertEqual(UserRole.objects.filter(user=borrower_user).count(), 1)
            self.assertEqual(UserRole.objects.filter(user=auditor_user).count(), 1)
            self.assertTrue(
                Role.objects.get(role_code="ADMIN").permissions.filter(permission_code="menu.system_management").exists()
            )
            self.assertTrue(
                Role.objects.get(role_code="ADMIN").permissions.filter(permission_code="button.system.health.detail").exists()
            )
            self.assertTrue(
                Role.objects.get(role_code="BORROWER").permissions.filter(permission_code="menu.borrow_center").exists()
            )
            self.assertFalse(
                Role.objects.get(role_code="BORROWER").permissions.filter(permission_code="menu.archive_center").exists()
            )
            self.assertTrue(
                Role.objects.get(role_code="ARCHIVIST").permissions.filter(
                    permission_code="button.notification.reminder.dispatch"
                ).exists()
            )
            self.assertTrue(
                Role.objects.get(role_code="AUDITOR").permissions.filter(permission_code="menu.report_center").exists()
            )
            self.assertFalse(
                Role.objects.get(role_code="AUDITOR").permissions.filter(permission_code="menu.archive_center").exists()
            )
            self.assertFalse(
                Role.objects.get(role_code="AUDITOR").permissions.filter(permission_code="menu.destruction_center").exists()
            )
            self.assertFalse(
                Role.objects.get(role_code="BORROWER").permissions.filter(permission_code="menu.system_management").exists()
            )

            business_department = Department.objects.get(dept_code="BUS")
            self.assertEqual(business_department.approver_user_id, admin_user.id)

            content = account_file.read_text(encoding="utf-8")
            self.assertIn("| 管理员 | admin | Admin12345 |", content)
            self.assertIn("| 档案员 | archivist | Archivist12345 |", content)
            self.assertIn("| 借阅人 | borrower | Borrower12345 |", content)
            self.assertIn("| 审计员 | auditor | Auditor12345 |", content)
