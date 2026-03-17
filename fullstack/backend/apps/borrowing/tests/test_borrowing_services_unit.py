from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import SecurityClearance
from apps.archives.models import ArchiveRecord, ArchiveStatus, ArchiveStorageLocation
from apps.borrowing.models import (
    BorrowApplication,
    BorrowApplicationStatus,
    BorrowReminderSendStatus,
    BorrowReminderType,
)
from apps.borrowing.services import (
    calculate_overdue_days,
    create_email_reminder_record,
    resolve_borrow_reminder_type,
    sync_borrow_application_overdue_state,
    validate_borrow_application_creation,
)
from apps.notifications.services import process_email_task
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


@override_settings(BORROW_REMINDER_BEFORE_DUE_DAYS=3)
class BorrowingServicesUnitTests(TestCase):
    def setUp(self) -> None:
        self.department = Department.objects.create(
            dept_code="UNIT_BORROW",
            dept_name="借阅单元测试部",
        )
        sync_department_hierarchy(self.department)

        self.applicant = User.objects.create_user(
            username="borrow_unit_user",
            password="BorrowUnit12345",
            real_name="借阅单元测试用户",
            dept=self.department,
            email="borrow.unit@example.com",
            security_clearance_level=SecurityClearance.INTERNAL,
            status=True,
        )
        self.approver = User.objects.create_user(
            username="borrow_unit_approver",
            password="BorrowApprover12345",
            real_name="借阅审批人",
            dept=self.department,
            security_clearance_level=SecurityClearance.SECRET,
            status=True,
        )
        self.department.approver_user_id = self.approver.id
        self.department.save(update_fields=["approver_user_id", "updated_at"])

        self.location = ArchiveStorageLocation.objects.create(
            warehouse_name="二号库房",
            area_name="B区",
            cabinet_code="G02",
            rack_code="J02",
            layer_code="L02",
            box_code="H02",
            status=True,
            created_by=self.approver.id,
            updated_by=self.approver.id,
        )

    def create_archive(self, *, archive_code: str, status: str = ArchiveStatus.ON_SHELF) -> ArchiveRecord:
        return ArchiveRecord.objects.create(
            archive_code=archive_code,
            title=f"{archive_code} 借阅测试档案",
            year=2026,
            retention_period="长期",
            security_level=SecurityClearance.INTERNAL,
            status=status,
            responsible_dept=self.department,
            responsible_person="责任人乙",
            summary="借阅服务层单元测试数据。",
            location=self.location,
            created_by=self.approver.id,
            updated_by=self.approver.id,
        )

    def create_application(
        self,
        *,
        archive: ArchiveRecord,
        status: str,
        expected_return_at,
    ) -> BorrowApplication:
        return BorrowApplication.objects.create(
            application_no=f"BORUNIT{BorrowApplication.objects.count() + 1:04d}",
            archive=archive,
            applicant=self.applicant,
            applicant_dept=self.department,
            purpose="单元测试借阅用途",
            expected_return_at=expected_return_at,
            status=status,
            current_approver=self.approver if status == BorrowApplicationStatus.PENDING_APPROVAL else None,
            submitted_at=timezone.now(),
            created_by=self.applicant.id,
            updated_by=self.applicant.id,
        )

    def test_calculate_overdue_days_should_cover_boundary_values(self) -> None:
        expected_return_at = timezone.now()

        self.assertEqual(calculate_overdue_days(expected_return_at, expected_return_at), 0)
        self.assertEqual(calculate_overdue_days(expected_return_at, expected_return_at + timedelta(hours=1)), 1)
        self.assertEqual(calculate_overdue_days(expected_return_at, expected_return_at + timedelta(days=2)), 2)

    def test_resolve_borrow_reminder_type_should_cover_before_due_due_today_and_overdue(self) -> None:
        archive = self.create_archive(archive_code="A2026-BU001")
        now = timezone.now()

        before_due_application = self.create_application(
            archive=archive,
            status=BorrowApplicationStatus.CHECKED_OUT,
            expected_return_at=now + timedelta(days=3),
        )
        due_today_application = self.create_application(
            archive=self.create_archive(archive_code="A2026-BU002"),
            status=BorrowApplicationStatus.CHECKED_OUT,
            expected_return_at=now,
        )
        overdue_application = self.create_application(
            archive=self.create_archive(archive_code="A2026-BU003"),
            status=BorrowApplicationStatus.CHECKED_OUT,
            expected_return_at=now - timedelta(days=1),
        )

        self.assertEqual(resolve_borrow_reminder_type(before_due_application, now), BorrowReminderType.BEFORE_DUE)
        self.assertEqual(resolve_borrow_reminder_type(due_today_application, now), BorrowReminderType.DUE_TODAY)
        self.assertEqual(resolve_borrow_reminder_type(overdue_application, now), BorrowReminderType.OVERDUE)

    def test_sync_borrow_application_overdue_state_should_switch_application_to_overdue(self) -> None:
        archive = self.create_archive(archive_code="A2026-BU004", status=ArchiveStatus.BORROWED)
        application = self.create_application(
            archive=archive,
            status=BorrowApplicationStatus.CHECKED_OUT,
            expected_return_at=timezone.now() - timedelta(days=2),
        )

        synced_application = sync_borrow_application_overdue_state(application)

        synced_application.refresh_from_db()
        self.assertEqual(synced_application.status, BorrowApplicationStatus.OVERDUE)
        self.assertTrue(synced_application.is_overdue)
        self.assertGreaterEqual(synced_application.overdue_days, 2)

    def test_validate_borrow_application_creation_should_reject_past_expected_return_time(self) -> None:
        archive = self.create_archive(archive_code="A2026-BU005")

        with self.assertRaisesMessage(ValidationError, "预计归还时间必须晚于当前时间。"):
            validate_borrow_application_creation(
                archive=archive,
                applicant=self.applicant,
                expected_return_at=timezone.now() - timedelta(minutes=1),
            )

    @override_settings(
        CELERY_TASK_ALWAYS_EAGER=False,
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    )
    def test_email_reminder_record_should_keep_pending_until_email_task_is_processed(self) -> None:
        archive = self.create_archive(archive_code="A2026-BU006", status=ArchiveStatus.BORROWED)
        application = self.create_application(
            archive=archive,
            status=BorrowApplicationStatus.OVERDUE,
            expected_return_at=timezone.now() - timedelta(days=2),
        )

        with patch("apps.notifications.tasks.send_email_task.delay") as mocked_delay:
            reminder_record = create_email_reminder_record(
                application=application,
                receiver_user=self.applicant,
                reminder_type=BorrowReminderType.OVERDUE,
                content="超期催还测试",
            )

        reminder_record.refresh_from_db()
        reminder_record.email_task.refresh_from_db()

        self.assertIsNotNone(reminder_record.email_task_id)
        self.assertEqual(reminder_record.send_status, BorrowReminderSendStatus.PENDING)
        self.assertEqual(reminder_record.email_task.send_status, "PENDING")
        mocked_delay.assert_called_once_with(reminder_record.email_task_id)

        process_email_task(reminder_record.email_task_id)
        reminder_record.refresh_from_db()
        reminder_record.email_task.refresh_from_db()

        self.assertEqual(reminder_record.email_task.send_status, "SUCCESS")
        self.assertEqual(reminder_record.send_status, BorrowReminderSendStatus.SUCCESS)
