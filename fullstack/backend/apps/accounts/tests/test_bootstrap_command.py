from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.accounts.models import Role, SystemPermission, UserRole
from apps.archives.models import ArchiveFile, ArchiveRecord, ArchiveStorageLocation
from apps.audit.models import AuditLog
from apps.borrowing.models import BorrowApplication, BorrowApplicationStatus
from apps.destruction.models import DestroyApplication, DestroyApplicationStatus
from apps.digitization.models import ScanTask
from apps.notifications.models import EmailTask, SystemNotification
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

    def test_bootstrap_system_should_preserve_existing_passwords_when_requested(self) -> None:
        with TemporaryDirectory() as temp_dir:
            account_file = Path(temp_dir) / "accounts.md"

            call_command(
                "bootstrap_system",
                username="admin",
                password="Admin12345",
                real_name="系统管理员",
                account_file=str(account_file),
            )

            admin_user = User.objects.get(username="admin")
            admin_user.set_password("CustomAdmin98765")
            admin_user.save(update_fields=["password"])

            call_command(
                "bootstrap_system",
                username="admin",
                password="Admin12345",
                real_name="系统管理员",
                account_file=str(account_file),
                preserve_existing_passwords=True,
            )

            admin_user.refresh_from_db()
            self.assertTrue(admin_user.check_password("CustomAdmin98765"))
            self.assertFalse(admin_user.check_password("Admin12345"))
            self.assertIn("| 管理员 | admin | 沿用已有密码 |", account_file.read_text(encoding="utf-8"))

    def test_check_bootstrap_state_should_report_required_before_bootstrap_and_ready_after_bootstrap(self) -> None:
        with TemporaryDirectory() as temp_dir:
            account_file = Path(temp_dir) / "accounts.md"

            output = StringIO()
            call_command(
                "check_bootstrap_state",
                username="admin",
                dept_code="ROOT",
                account_file=str(account_file),
                stdout=output,
            )
            self.assertIn("BOOTSTRAP_REQUIRED=true", output.getvalue())

            call_command(
                "bootstrap_system",
                username="admin",
                password="Admin12345",
                real_name="系统管理员",
                account_file=str(account_file),
            )

            output = StringIO()
            call_command(
                "check_bootstrap_state",
                username="admin",
                dept_code="ROOT",
                account_file=str(account_file),
                stdout=output,
            )
            self.assertIn("BOOTSTRAP_REQUIRED=false", output.getvalue())


class BootstrapDemoDataCommandTests(TestCase):
    def setUp(self) -> None:
        self.temp_media_dir = TemporaryDirectory()
        self.media_override = override_settings(MEDIA_ROOT=self.temp_media_dir.name)
        self.media_override.enable()

    def tearDown(self) -> None:
        self.media_override.disable()
        self.temp_media_dir.cleanup()
        super().tearDown()

    def test_bootstrap_demo_data_should_create_idempotent_business_demo_data(self) -> None:
        with TemporaryDirectory() as temp_dir:
            account_file = Path(temp_dir) / "accounts.md"

            call_command(
                "bootstrap_system",
                username="admin",
                password="Admin12345",
                real_name="系统管理员",
                account_file=str(account_file),
            )

            call_command("bootstrap_demo_data", admin_username="admin")
            call_command("bootstrap_demo_data", admin_username="admin")

            self.assertEqual(ArchiveStorageLocation.objects.count(), 2)
            self.assertEqual(ArchiveRecord.objects.count(), 6)
            self.assertEqual(ScanTask.objects.count(), 2)
            self.assertEqual(BorrowApplication.objects.count(), 3)
            self.assertEqual(DestroyApplication.objects.count(), 2)
            self.assertEqual(SystemNotification.objects.count(), 5)
            self.assertEqual(EmailTask.objects.count(), 1)
            self.assertEqual(AuditLog.objects.filter(module_name="DEMO").count(), 4)

            contract_archive = ArchiveRecord.objects.get(archive_code="DEMO-ARC-002")
            self.assertEqual(contract_archive.barcodes.count(), 2)

            contract_file = ArchiveFile.objects.get(archive=contract_archive, file_name="DEMO-ARC-002.pdf")
            self.assertTrue(Path(self.temp_media_dir.name, contract_file.file_path).exists())
            self.assertTrue(Path(self.temp_media_dir.name, contract_file.thumbnail_path).exists())

            overdue_application = BorrowApplication.objects.get(application_no="DEMO-BORROW-002")
            self.assertEqual(overdue_application.status, BorrowApplicationStatus.OVERDUE)
            self.assertTrue(overdue_application.reminder_records.filter(channel="SITE").exists())
            self.assertTrue(overdue_application.reminder_records.filter(channel="EMAIL").exists())

            executed_destroy = DestroyApplication.objects.get(application_no="DEMO-DESTROY-002")
            self.assertEqual(executed_destroy.status, DestroyApplicationStatus.EXECUTED)
            self.assertTrue(executed_destroy.execution_record.attachments.exists())
