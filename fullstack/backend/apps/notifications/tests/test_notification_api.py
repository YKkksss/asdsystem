from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import DataScope, Role, SecurityClearance
from apps.accounts.services import assign_roles_to_user
from apps.archives.models import ArchiveRecord, ArchiveStatus, ArchiveStorageLocation
from apps.borrowing.models import BorrowApplication
from apps.notifications.models import NotificationType, SystemNotification
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    BORROW_REMINDER_BEFORE_DUE_DAYS=3,
    BORROW_REMINDER_ESCALATE_DAYS=3,
)
class NotificationApiTests(APITestCase):
    def setUp(self) -> None:
        self.client = APIClient()

        self.department = Department.objects.create(
            dept_code="ROOT",
            dept_name="总部",
        )
        sync_department_hierarchy(self.department)

        self.archivist_role = Role.objects.create(
            role_code="ARCHIVIST",
            role_name="档案员",
            data_scope=DataScope.DEPT,
            status=True,
        )
        self.borrower_role = Role.objects.create(
            role_code="BORROWER",
            role_name="借阅人",
            data_scope=DataScope.SELF,
            status=True,
        )

        self.approver_user = User.objects.create_user(
            username="leader_notify",
            password="Leader12345",
            real_name="部门负责人",
            dept=self.department,
            email="leader@example.com",
            is_staff=True,
            security_clearance_level=SecurityClearance.SECRET,
        )
        assign_roles_to_user(self.approver_user, [self.borrower_role.id])

        self.archivist_user = User.objects.create_user(
            username="archivist_notify",
            password="Archivist123",
            real_name="档案员甲",
            dept=self.department,
            email="archivist@example.com",
            is_staff=True,
            security_clearance_level=SecurityClearance.SECRET,
        )
        assign_roles_to_user(self.archivist_user, [self.archivist_role.id])

        self.borrower_user = User.objects.create_user(
            username="borrower_notify",
            password="Borrower123",
            real_name="借阅人甲",
            dept=self.department,
            email="borrower@example.com",
            security_clearance_level=SecurityClearance.INTERNAL,
        )
        assign_roles_to_user(self.borrower_user, [self.borrower_role.id])

        self.department.approver_user_id = self.approver_user.id
        self.department.save(update_fields=["approver_user_id", "updated_at"])

        self.location = ArchiveStorageLocation.objects.create(
            warehouse_name="一号库房",
            area_name="A区",
            cabinet_code="G01",
            rack_code="J01",
            layer_code="L01",
            box_code="H01",
            status=True,
            created_by=self.archivist_user.id,
            updated_by=self.archivist_user.id,
        )

    def create_checked_out_application(self, *, archive_code: str, expected_return_at) -> int:
        archive = ArchiveRecord.objects.create(
            archive_code=archive_code,
            title=f"{archive_code} 档案",
            year=2026,
            retention_period="长期",
            security_level=SecurityClearance.INTERNAL,
            status=ArchiveStatus.ON_SHELF,
            responsible_dept=self.department,
            location=self.location,
            created_by=self.archivist_user.id,
            updated_by=self.archivist_user.id,
        )

        self.client.force_authenticate(self.borrower_user)
        application_id = self.client.post(
            "/api/v1/borrowing/applications/",
            {
                "archive_id": archive.id,
                "purpose": "催还通知测试",
                "expected_return_at": expected_return_at.isoformat(),
            },
            format="json",
        ).json()["data"]["id"]

        self.client.force_authenticate(self.approver_user)
        self.client.post(
            f"/api/v1/borrowing/applications/{application_id}/approve/",
            {"action": "APPROVE", "opinion": "通过"},
            format="json",
        )

        self.client.force_authenticate(self.archivist_user)
        self.client.post(
            f"/api/v1/borrowing/applications/{application_id}/checkout/",
            {"checkout_note": "已借出"},
            format="json",
        )

        return application_id

    def create_notification(
        self,
        *,
        user,
        title: str,
        notification_type: str = NotificationType.SYSTEM,
        is_read: bool = False,
    ) -> SystemNotification:
        notification = SystemNotification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            content=f"{title} 内容",
            biz_type="test_business",
            biz_id=1,
            is_read=is_read,
        )
        if is_read:
            notification.read_at = timezone.now()
            notification.save(update_fields=["read_at", "updated_at"])
        return notification

    def test_dispatch_reminder_should_create_notification_and_email_without_duplicate(self) -> None:
        application_id = self.create_checked_out_application(
            archive_code="A2026-N001",
            expected_return_at=timezone.now() + timedelta(days=3),
        )

        self.client.force_authenticate(self.archivist_user)
        first_response = self.client.post("/api/v1/borrowing/reminders/dispatch/", format="json")
        second_response = self.client.post("/api/v1/borrowing/reminders/dispatch/", format="json")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.json()["data"]["record_count"], 2)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(second_response.json()["data"]["record_count"], 0)

        self.client.force_authenticate(self.borrower_user)
        notification_response = self.client.get("/api/v1/notifications/messages/")
        summary_response = self.client.get("/api/v1/notifications/summary/")
        reminder_notifications = [
            item for item in notification_response.json()["data"] if item["notification_type"] == NotificationType.BORROW_REMINDER
        ]

        self.assertEqual(notification_response.status_code, 200)
        self.assertEqual(len(reminder_notifications), 1)
        self.assertEqual(summary_response.json()["data"]["unread_count"], 2)
        self.assertEqual(summary_response.json()["data"]["reminder_unread_count"], 1)

        notification_id = reminder_notifications[0]["id"]
        mark_read_response = self.client.post(
            f"/api/v1/notifications/messages/{notification_id}/mark-read/",
            format="json",
        )
        self.assertEqual(mark_read_response.status_code, 200)

        summary_after_read = self.client.get("/api/v1/notifications/summary/")
        self.assertEqual(summary_after_read.json()["data"]["unread_count"], 1)
        self.assertEqual(summary_after_read.json()["data"]["reminder_unread_count"], 0)
        self.assertEqual(BorrowApplication.objects.get(id=application_id).status, "CHECKED_OUT")

    def test_mark_all_read_should_batch_update_current_user_notifications(self) -> None:
        self.create_checked_out_application(
            archive_code="A2026-N003",
            expected_return_at=timezone.now() + timedelta(days=3),
        )

        self.client.force_authenticate(self.archivist_user)
        dispatch_response = self.client.post("/api/v1/borrowing/reminders/dispatch/", format="json")
        self.assertEqual(dispatch_response.status_code, 200)

        self.client.force_authenticate(self.borrower_user)
        unread_count = SystemNotification.objects.filter(user=self.borrower_user, is_read=False).count()
        mark_all_response = self.client.post("/api/v1/notifications/messages/mark-all-read/", format="json")
        summary_response = self.client.get("/api/v1/notifications/summary/")

        self.assertEqual(mark_all_response.status_code, 200)
        self.assertEqual(mark_all_response.json()["data"]["updated_count"], unread_count)
        self.assertEqual(summary_response.json()["data"]["unread_count"], 0)

    def test_mark_read_should_be_idempotent_for_already_read_notification(self) -> None:
        notification = self.create_notification(
            user=self.borrower_user,
            title="已读通知测试",
            is_read=True,
        )
        original_read_at = notification.read_at

        self.client.force_authenticate(self.borrower_user)
        response = self.client.post(
            f"/api/v1/notifications/messages/{notification.id}/mark-read/",
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        notification.refresh_from_db()
        self.assertEqual(notification.read_at, original_read_at)

    def test_user_should_not_mark_other_user_notification_as_read(self) -> None:
        notification = self.create_notification(
            user=self.approver_user,
            title="越权已读测试",
        )

        self.client.force_authenticate(self.borrower_user)
        response = self.client.post(
            f"/api/v1/notifications/messages/{notification.id}/mark-read/",
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)

    def test_mark_all_read_should_return_zero_when_no_unread_notifications(self) -> None:
        self.create_notification(
            user=self.borrower_user,
            title="已读通知一",
            is_read=True,
        )
        self.create_notification(
            user=self.borrower_user,
            title="已读通知二",
            is_read=True,
        )

        self.client.force_authenticate(self.borrower_user)
        response = self.client.post("/api/v1/notifications/messages/mark-all-read/", format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["updated_count"], 0)

    def test_overdue_dispatch_should_escalate_to_approver_and_archive_manager(self) -> None:
        application_id = self.create_checked_out_application(
            archive_code="A2026-N002",
            expected_return_at=timezone.now() + timedelta(days=1),
        )
        application = BorrowApplication.objects.get(id=application_id)
        application.expected_return_at = timezone.now() - timedelta(days=4)
        application.save(update_fields=["expected_return_at", "updated_at"])

        self.client.force_authenticate(self.archivist_user)
        response = self.client.post("/api/v1/borrowing/reminders/dispatch/", format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["record_count"], 6)

        application.refresh_from_db()
        self.assertEqual(application.status, "OVERDUE")
        self.assertEqual(application.overdue_days, 4)

        self.client.force_authenticate(self.borrower_user)
        borrower_notifications = self.client.get("/api/v1/notifications/messages/")
        self.assertEqual(
            len(
                [
                    item
                    for item in borrower_notifications.json()["data"]
                    if item["notification_type"] == NotificationType.BORROW_REMINDER
                ]
            ),
            1,
        )

        self.client.force_authenticate(self.approver_user)
        approver_notifications = self.client.get("/api/v1/notifications/messages/")
        self.assertEqual(
            len(
                [
                    item
                    for item in approver_notifications.json()["data"]
                    if item["notification_type"] == NotificationType.BORROW_REMINDER
                ]
            ),
            1,
        )

        self.client.force_authenticate(self.archivist_user)
        archivist_notifications = self.client.get("/api/v1/notifications/messages/")
        self.assertEqual(
            len(
                [
                    item
                    for item in archivist_notifications.json()["data"]
                    if item["notification_type"] == NotificationType.BORROW_REMINDER
                ]
            ),
            1,
        )

        self.client.force_authenticate(self.approver_user)
        borrow_detail_response = self.client.get(f"/api/v1/borrowing/applications/{application_id}/")
        self.assertEqual(borrow_detail_response.status_code, 200)
        self.assertEqual(borrow_detail_response.json()["data"]["id"], application_id)
