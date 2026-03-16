from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import DataScope, Role, SecurityClearance, SystemPermission
from apps.accounts.services import assign_permissions_to_role, assign_roles_to_user
from apps.archives.models import ArchiveRecord, ArchiveStatus, ArchiveStorageLocation
from apps.digitization.models import ScanTask, ScanTaskItem
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
        self.borrow_approve_permission = SystemPermission.objects.create(
            permission_code="button.borrow.approve",
            permission_name="审批借阅申请",
            permission_type="BUTTON",
            module_name="borrowing",
            sort_order=290,
            status=True,
        )
        self.borrow_approver_role = Role.objects.create(
            role_code="BORROW_APPROVER",
            role_name="借阅审批人",
            data_scope=DataScope.DEPT,
            status=True,
        )
        assign_permissions_to_role(self.borrow_approver_role, [self.borrow_approve_permission.id])
        self.reminder_dispatch_permission, _ = SystemPermission.objects.get_or_create(
            permission_code="button.notification.reminder.dispatch",
            defaults={
                "permission_name": "执行催还扫描",
                "permission_type": "BUTTON",
                "module_name": "notifications",
                "status": True,
                "sort_order": 325,
            },
        )
        self.reminder_dispatch_permission.permission_name = "执行催还扫描"
        self.reminder_dispatch_permission.permission_type = "BUTTON"
        self.reminder_dispatch_permission.module_name = "notifications"
        self.reminder_dispatch_permission.status = True
        self.reminder_dispatch_permission.sort_order = 325
        self.reminder_dispatch_permission.save(
            update_fields=[
                "permission_name",
                "permission_type",
                "module_name",
                "status",
                "sort_order",
                "updated_at",
            ]
        )
        self.reminder_operator_role = Role.objects.create(
            role_code="REMINDER_OPERATOR",
            role_name="催还操作员",
            data_scope=DataScope.DEPT,
            status=True,
        )
        assign_permissions_to_role(self.reminder_operator_role, [self.reminder_dispatch_permission.id])

        self.approver_user = User.objects.create_user(
            username="leader_notify",
            password="Leader12345",
            real_name="部门负责人",
            dept=self.department,
            email="leader@example.com",
            is_staff=True,
            security_clearance_level=SecurityClearance.SECRET,
        )
        assign_roles_to_user(self.approver_user, [self.borrower_role.id, self.borrow_approver_role.id])

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

        self.reminder_operator_user = User.objects.create_user(
            username="reminder_operator",
            password="Reminder123",
            real_name="催还操作员",
            dept=self.department,
            email="reminder@example.com",
            is_staff=True,
            security_clearance_level=SecurityClearance.SECRET,
        )
        assign_roles_to_user(self.reminder_operator_user, [self.reminder_operator_role.id])

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
        biz_type: str | None = "test_business",
        biz_id: int | None = 1,
    ) -> SystemNotification:
        notification = SystemNotification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            content=f"{title} 内容",
            biz_type=biz_type,
            biz_id=biz_id,
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
        self.assertEqual(
            reminder_notifications[0]["route_path"],
            f"/borrowing/applications?applicationId={application_id}",
        )
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

    def test_user_with_dispatch_permission_should_dispatch_reminders(self) -> None:
        self.create_checked_out_application(
            archive_code="A2026-N010",
            expected_return_at=timezone.now() + timedelta(days=3),
        )

        self.client.force_authenticate(self.reminder_operator_user)
        response = self.client.post("/api/v1/borrowing/reminders/dispatch/", format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["record_count"], 2)

    def test_borrower_without_dispatch_permission_should_be_forbidden(self) -> None:
        self.client.force_authenticate(self.borrower_user)

        response = self.client.post("/api/v1/borrowing/reminders/dispatch/", format="json")

        self.assertEqual(response.status_code, 403)

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

    def test_notification_list_should_support_optional_pagination(self) -> None:
        for index in range(5):
            self.create_notification(
                user=self.borrower_user,
                title=f"分页通知{index + 1}",
                notification_type=NotificationType.SYSTEM,
            )

        self.client.force_authenticate(self.borrower_user)
        response = self.client.get("/api/v1/notifications/messages/", {"page": 2, "page_size": 2})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["pagination"]["page"], 2)
        self.assertEqual(response.json()["data"]["pagination"]["page_size"], 2)
        self.assertEqual(response.json()["data"]["pagination"]["total"], 5)
        self.assertEqual(response.json()["data"]["pagination"]["total_pages"], 3)
        self.assertEqual(len(response.json()["data"]["items"]), 2)

    def test_notification_position_should_return_target_page(self) -> None:
        self.create_notification(
            user=self.borrower_user,
            title="已读通知",
            is_read=True,
        )
        first_unread = self.create_notification(
            user=self.borrower_user,
            title="未读通知一",
        )
        second_unread = self.create_notification(
            user=self.borrower_user,
            title="未读通知二",
        )
        third_unread = self.create_notification(
            user=self.borrower_user,
            title="未读通知三",
        )

        self.client.force_authenticate(self.borrower_user)
        response = self.client.get(
            f"/api/v1/notifications/messages/{first_unread.id}/position/",
            {"page_size": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["page"], 2)
        self.assertEqual(response.json()["data"]["page_size"], 2)
        self.assertEqual(response.json()["data"]["row_index"], 2)

    def test_notification_list_should_return_archive_route_path(self) -> None:
        archive = ArchiveRecord.objects.create(
            archive_code="A2026-N999",
            title="通知路由档案",
            year=2026,
            retention_period="长期",
            security_level=SecurityClearance.INTERNAL,
            status=ArchiveStatus.ON_SHELF,
            responsible_dept=self.department,
            created_by=self.archivist_user.id,
            updated_by=self.archivist_user.id,
        )
        self.create_notification(
            user=self.borrower_user,
            title="档案通知",
            biz_type="archive_record",
            biz_id=archive.id,
        )

        self.client.force_authenticate(self.borrower_user)
        response = self.client.get("/api/v1/notifications/messages/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"][0]["route_path"],
            f"/archives/records?archiveId={archive.id}",
        )

    def test_notification_list_should_return_scan_task_item_route_path(self) -> None:
        archive = ArchiveRecord.objects.create(
            archive_code="A2026-N998",
            title="扫描任务通知档案",
            year=2026,
            retention_period="长期",
            security_level=SecurityClearance.INTERNAL,
            status=ArchiveStatus.PENDING_SCAN,
            responsible_dept=self.department,
            created_by=self.archivist_user.id,
            updated_by=self.archivist_user.id,
        )
        scan_task = ScanTask.objects.create(
            task_no="SCAN-ROUTE-001",
            task_name="通知深链扫描任务",
            assigned_user_id=self.archivist_user.id,
            assigned_by=self.archivist_user.id,
            created_by=self.archivist_user.id,
            updated_by=self.archivist_user.id,
        )
        task_item = ScanTaskItem.objects.create(
            task=scan_task,
            archive=archive,
            assignee_user_id=self.archivist_user.id,
        )
        self.create_notification(
            user=self.archivist_user,
            title="扫描明细通知",
            biz_type="scan_task_item",
            biz_id=task_item.id,
        )

        self.client.force_authenticate(self.archivist_user)
        response = self.client.get("/api/v1/notifications/messages/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"][0]["route_path"],
            f"/digitization/scan-tasks/{scan_task.id}?itemId={task_item.id}",
        )

    def test_notification_list_should_return_destroy_application_route_path(self) -> None:
        self.create_notification(
            user=self.approver_user,
            title="销毁审批通知",
            biz_type="destroy_application",
            biz_id=88,
        )

        self.client.force_authenticate(self.approver_user)
        response = self.client.get("/api/v1/notifications/messages/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"][0]["route_path"],
            "/destruction/applications?applicationId=88",
        )

    def test_notification_list_should_return_report_export_route_path(self) -> None:
        self.create_notification(
            user=self.archivist_user,
            title="报表导出完成",
            biz_type="report_export",
            biz_id=None,
        )

        self.client.force_authenticate(self.archivist_user)
        response = self.client.get("/api/v1/notifications/messages/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"][0]["route_path"], "/reports/center")

    def test_notification_list_should_fallback_to_notification_center_when_biz_type_missing(self) -> None:
        notification = self.create_notification(
            user=self.borrower_user,
            title="通用系统通知",
            biz_type=None,
            biz_id=None,
        )

        self.client.force_authenticate(self.borrower_user)
        response = self.client.get("/api/v1/notifications/messages/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"][0]["route_path"],
            f"/notifications/messages?notificationId={notification.id}",
        )
