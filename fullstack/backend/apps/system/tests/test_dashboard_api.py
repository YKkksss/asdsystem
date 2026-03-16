from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import DataScope, Role, SecurityClearance
from apps.accounts.services import assign_roles_to_user
from apps.archives.models import ArchiveRecord, ArchiveStatus
from apps.borrowing.models import BorrowApplication, BorrowApplicationStatus, BorrowReturnRecord, BorrowReturnStatus
from apps.destruction.models import DestroyApplication, DestroyApplicationStatus
from apps.notifications.models import NotificationType, SystemNotification
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class DashboardApiTests(TestCase):
    def setUp(self) -> None:
        self.base_now = timezone.now()
        self.root_department = Department.objects.create(
            dept_code="ROOT",
            dept_name="总部",
        )
        sync_department_hierarchy(self.root_department)
        self.business_department = Department.objects.create(
            dept_code="BUS",
            dept_name="业务部",
            parent=self.root_department,
        )
        sync_department_hierarchy(self.business_department)

        self.admin_role = Role.objects.create(
            role_code="ADMIN",
            role_name="管理员",
            data_scope=DataScope.ALL,
            status=True,
        )
        self.borrower_role = Role.objects.create(
            role_code="BORROWER",
            role_name="借阅人",
            data_scope=DataScope.SELF,
            status=True,
        )

        self.admin_user = User.objects.create_user(
            username="dashboard_admin",
            password="DashboardAdmin12345",
            real_name="工作台管理员",
            dept=self.root_department,
            is_staff=True,
            security_clearance_level=SecurityClearance.TOP_SECRET,
        )
        assign_roles_to_user(self.admin_user, [self.admin_role.id])

        self.borrower_user = User.objects.create_user(
            username="dashboard_borrower",
            password="DashboardBorrower12345",
            real_name="工作台借阅人",
            dept=self.business_department,
            is_staff=False,
            security_clearance_level=SecurityClearance.INTERNAL,
        )
        assign_roles_to_user(self.borrower_user, [self.borrower_role.id])

        self.archive_on_shelf = ArchiveRecord.objects.create(
            archive_code="ARCH-DASH-001",
            title="工作台联调档案一",
            year=2024,
            retention_period="30年",
            security_level=SecurityClearance.INTERNAL,
            status=ArchiveStatus.ON_SHELF,
            responsible_dept=self.business_department,
            responsible_person=self.borrower_user.real_name,
            created_by=self.admin_user.id,
            updated_by=self.admin_user.id,
        )
        self.archive_pending_scan = ArchiveRecord.objects.create(
            archive_code="ARCH-DASH-002",
            title="工作台联调档案二",
            year=2024,
            retention_period="长期",
            security_level=SecurityClearance.INTERNAL,
            status=ArchiveStatus.PENDING_SCAN,
            responsible_dept=self.business_department,
            created_by=self.admin_user.id,
            updated_by=self.admin_user.id,
        )

        self.pending_approval_application = BorrowApplication.objects.create(
            application_no="BOR-DASH-001",
            archive=self.archive_on_shelf,
            applicant=self.borrower_user,
            applicant_dept=self.business_department,
            purpose="用于工作台审批统计联调",
            expected_return_at=self.base_now + timedelta(days=4),
            status=BorrowApplicationStatus.PENDING_APPROVAL,
            current_approver=self.admin_user,
            submitted_at=self.base_now - timedelta(hours=2),
            created_by=self.borrower_user.id,
            updated_by=self.borrower_user.id,
        )
        self.checked_out_application = BorrowApplication.objects.create(
            application_no="BOR-DASH-002",
            archive=self.archive_on_shelf,
            applicant=self.borrower_user,
            applicant_dept=self.business_department,
            purpose="用于工作台归还统计联调",
            expected_return_at=self.base_now - timedelta(days=6),
            status=BorrowApplicationStatus.OVERDUE,
            is_overdue=True,
            overdue_days=6,
            checkout_at=self.base_now - timedelta(days=15),
            created_by=self.borrower_user.id,
            updated_by=self.borrower_user.id,
        )
        self.returned_application = BorrowApplication.objects.create(
            application_no="BOR-DASH-003",
            archive=self.archive_on_shelf,
            applicant=self.borrower_user,
            applicant_dept=self.business_department,
            purpose="用于工作台归还趋势联调",
            expected_return_at=self.base_now - timedelta(days=3),
            status=BorrowApplicationStatus.RETURNED,
            submitted_at=self.base_now - timedelta(days=6),
            checkout_at=self.base_now - timedelta(days=5),
            returned_at=self.base_now - timedelta(days=2),
            created_by=self.borrower_user.id,
            updated_by=self.borrower_user.id,
        )
        BorrowReturnRecord.objects.create(
            application=self.checked_out_application,
            archive=self.archive_on_shelf,
            returned_by_user=self.borrower_user,
            return_status=BorrowReturnStatus.SUBMITTED,
            handover_type="PHOTO",
            handover_note="等待档案员确认。",
        )

        self.destroy_application = DestroyApplication.objects.create(
            application_no="DST-DASH-001",
            archive=self.archive_pending_scan,
            applicant=self.admin_user,
            applicant_dept=self.root_department,
            reason="用于工作台销毁统计联调",
            basis="测试依据",
            status=DestroyApplicationStatus.PENDING_APPROVAL,
            current_approver=self.admin_user,
            submitted_at=self.base_now - timedelta(hours=1),
            created_by=self.admin_user.id,
            updated_by=self.admin_user.id,
        )

        self.admin_system_notification = SystemNotification.objects.create(
            user=self.admin_user,
            notification_type=NotificationType.SYSTEM,
            title="管理员未读通知",
            content="请处理今日待办。",
        )
        self.admin_destroy_notification = SystemNotification.objects.create(
            user=self.admin_user,
            notification_type=NotificationType.DESTROY_APPROVAL,
            title="管理员销毁审批提醒",
            content="有一条销毁申请等待处理。",
            biz_type="destroy_application",
            biz_id=self.destroy_application.id,
        )
        self.borrower_reminder_notification = SystemNotification.objects.create(
            user=self.borrower_user,
            notification_type=NotificationType.BORROW_REMINDER,
            title="借阅人催还提醒",
            content="你有一条超期借阅记录。",
            biz_type="borrow_application",
            biz_id=self.checked_out_application.id,
        )

    def test_dashboard_should_require_authentication(self) -> None:
        response = self.client.get("/api/v1/system/dashboard/")

        self.assertEqual(response.status_code, 401)

    def test_admin_dashboard_should_return_staff_summary(self) -> None:
        self.client.force_login(self.admin_user)

        response = self.client.get("/api/v1/system/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["headline"], "档案业务工作台")
        payload = response.json()["data"]
        summary_cards = {item["key"]: item for item in payload["summary_cards"]}
        todo_cards = {item["key"]: item for item in payload["todo_cards"]}
        workflow_sections = {item["key"]: item for item in payload["workflow_sections"]}
        signal_cards = {item["key"]: item for item in payload["signal_cards"]}
        trend_sections = {item["key"]: item for item in payload["trend_sections"]}
        pending_task_items = payload["pending_task_items"]
        recent_notifications = {item["key"]: item for item in payload["recent_notifications"]}

        self.assertEqual(summary_cards["archive_total"]["value"], 2)
        self.assertEqual(summary_cards["unread_notifications"]["value"], 2)
        self.assertEqual(todo_cards["pending_borrow_approvals"]["value"], 1)
        self.assertEqual(todo_cards["pending_returns"]["value"], 1)
        self.assertEqual(payload["priority_focus"]["key"], "pending_borrow_approvals")
        self.assertEqual(workflow_sections["archive_flow"]["title"], "档案流转看板")
        self.assertEqual(len(workflow_sections["borrow_flow"]["items"]), 4)
        self.assertEqual(signal_cards["notification_reminder_signal"]["value"], 0)
        self.assertEqual(len(trend_sections), 3)
        self.assertEqual(len(trend_sections["borrow_submitted_trend"]["items"]), 7)
        self.assertEqual(len(trend_sections["borrow_returned_trend"]["items"]), 7)
        self.assertEqual(len(trend_sections["borrow_overdue_trend"]["items"]), 7)
        self.assertEqual(
            sum(item["value"] for item in trend_sections["borrow_submitted_trend"]["items"]),
            2,
        )
        self.assertEqual(
            sum(item["value"] for item in trend_sections["borrow_returned_trend"]["items"]),
            1,
        )
        self.assertGreaterEqual(
            max(item["value"] for item in trend_sections["borrow_overdue_trend"]["items"]),
            1,
        )
        self.assertEqual(pending_task_items[0]["badge"], "借阅审批")
        self.assertEqual(pending_task_items[1]["badge"], "归还验收")
        self.assertEqual(
            pending_task_items[0]["route_path"],
            f"/borrowing/approvals?applicationId={self.pending_approval_application.id}",
        )
        self.assertEqual(
            pending_task_items[1]["route_path"],
            f"/borrowing/returns?applicationId={self.checked_out_application.id}&mode=confirm",
        )
        self.assertEqual(
            recent_notifications[f"notification_{self.admin_destroy_notification.id}"]["route_path"],
            f"/destruction/applications?applicationId={self.destroy_application.id}",
        )
        self.assertEqual(
            recent_notifications[f"notification_{self.admin_system_notification.id}"]["route_path"],
            f"/notifications/messages?notificationId={self.admin_system_notification.id}",
        )

    def test_borrower_dashboard_should_return_personal_summary(self) -> None:
        self.client.force_login(self.borrower_user)

        response = self.client.get("/api/v1/system/dashboard/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["headline"], "我的档案业务工作台")
        payload = response.json()["data"]
        summary_cards = {item["key"]: item for item in payload["summary_cards"]}
        todo_cards = {item["key"]: item for item in payload["todo_cards"]}
        workflow_sections = {item["key"]: item for item in payload["workflow_sections"]}
        signal_cards = {item["key"]: item for item in payload["signal_cards"]}
        trend_sections = {item["key"]: item for item in payload["trend_sections"]}
        pending_task_items = payload["pending_task_items"]
        recent_notifications = payload["recent_notifications"]

        self.assertEqual(summary_cards["visible_archives"]["value"], 2)
        self.assertEqual(summary_cards["visible_archives"]["route_path"], "/borrowing/applications")
        self.assertEqual(summary_cards["my_applications"]["value"], 3)
        self.assertEqual(summary_cards["active_borrows"]["value"], 1)
        self.assertEqual(todo_cards["overdue_returns"]["value"], 1)
        self.assertEqual(todo_cards["reminder_unread_count"]["value"], 1)
        self.assertEqual(payload["priority_focus"]["key"], "overdue_returns")
        self.assertEqual(workflow_sections["borrow_flow"]["title"], "我的借阅流程")
        self.assertEqual(signal_cards["overdue_returns_signal"]["value"], 1)
        self.assertEqual(len(trend_sections), 3)
        self.assertEqual(len(trend_sections["borrow_submitted_trend"]["items"]), 7)
        self.assertEqual(
            sum(item["value"] for item in trend_sections["borrow_submitted_trend"]["items"]),
            2,
        )
        self.assertEqual(
            sum(item["value"] for item in trend_sections["borrow_returned_trend"]["items"]),
            1,
        )
        self.assertGreaterEqual(
            max(item["value"] for item in trend_sections["borrow_overdue_trend"]["items"]),
            1,
        )
        self.assertEqual(pending_task_items[0]["badge"], "超期归还")
        self.assertEqual(
            pending_task_items[0]["route_path"],
            f"/borrowing/returns?applicationId={self.checked_out_application.id}&mode=submit",
        )
        self.assertEqual(recent_notifications[0]["badge"], "催还提醒")
        self.assertEqual(
            recent_notifications[0]["route_path"],
            f"/borrowing/applications?applicationId={self.checked_out_application.id}",
        )
