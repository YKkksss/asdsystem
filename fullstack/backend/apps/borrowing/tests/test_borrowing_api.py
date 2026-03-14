import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import DataScope, Role, SecurityClearance
from apps.accounts.services import assign_roles_to_user
from apps.archives.models import ArchiveRecord, ArchiveStatus, ArchiveStorageLocation
from apps.notifications.models import NotificationType, SystemNotification
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class BorrowingApiTests(APITestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.media_root = tempfile.mkdtemp()
        self.media_override = override_settings(MEDIA_ROOT=self.media_root)
        self.media_override.enable()

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
        self.admin_role = Role.objects.create(
            role_code="ADMIN",
            role_name="管理员",
            data_scope=DataScope.ALL,
            status=True,
        )

        self.approver_user = User.objects.create_user(
            username="leader",
            password="Leader12345",
            real_name="部门负责人",
            dept=self.department,
            is_staff=True,
            security_clearance_level=SecurityClearance.SECRET,
        )
        assign_roles_to_user(self.approver_user, [self.borrower_role.id])

        self.archivist_user = User.objects.create_user(
            username="archivist",
            password="Archivist123",
            real_name="档案员甲",
            dept=self.department,
            is_staff=True,
            security_clearance_level=SecurityClearance.SECRET,
        )
        assign_roles_to_user(self.archivist_user, [self.archivist_role.id])

        self.borrower_user = User.objects.create_user(
            username="borrower",
            password="Borrower123",
            real_name="借阅人甲",
            dept=self.department,
            security_clearance_level=SecurityClearance.INTERNAL,
        )
        assign_roles_to_user(self.borrower_user, [self.borrower_role.id])

        self.admin_user = User.objects.create_user(
            username="admin",
            password="Admin12345",
            real_name="系统管理员",
            dept=self.department,
            is_staff=True,
            security_clearance_level=SecurityClearance.TOP_SECRET,
        )
        assign_roles_to_user(self.admin_user, [self.admin_role.id])

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

    def tearDown(self) -> None:
        self.media_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    def create_archive(self, *, archive_code: str, security_level: str) -> ArchiveRecord:
        return ArchiveRecord.objects.create(
            archive_code=archive_code,
            title=f"{archive_code} 测试档案",
            year=2026,
            retention_period="长期",
            security_level=security_level,
            status=ArchiveStatus.ON_SHELF,
            responsible_dept=self.department,
            responsible_person="测试责任人",
            summary="测试借阅流程用档案。",
            location=self.location,
            created_by=self.archivist_user.id,
            updated_by=self.archivist_user.id,
        )

    def assert_notification_exists(
        self,
        *,
        user,
        notification_type: str,
        title: str,
        biz_id: int,
    ) -> SystemNotification:
        notification = SystemNotification.objects.filter(
            user=user,
            notification_type=notification_type,
            title=title,
            biz_type="borrow_application",
            biz_id=biz_id,
        ).order_by("-id").first()
        self.assertIsNotNone(notification)
        return notification

    def test_borrow_application_workflow_should_complete_full_cycle_and_send_notifications(self) -> None:
        archive = self.create_archive(
            archive_code="A2026-B001",
            security_level=SecurityClearance.INTERNAL,
        )
        expected_return_at = (timezone.now() + timedelta(days=5)).isoformat()

        self.client.force_authenticate(self.borrower_user)
        create_response = self.client.post(
            "/api/v1/borrowing/applications/",
            {
                "archive_id": archive.id,
                "purpose": "业务查证",
                "expected_return_at": expected_return_at,
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, 201)
        application_id = create_response.json()["data"]["id"]
        self.assertEqual(create_response.json()["data"]["status"], "PENDING_APPROVAL")
        self.assertEqual(create_response.json()["data"]["current_approver_id"], self.approver_user.id)
        self.assert_notification_exists(
            user=self.approver_user,
            notification_type=NotificationType.BORROW_APPROVAL,
            title="档案借阅待审批",
            biz_id=application_id,
        )

        self.client.force_authenticate(self.approver_user)
        approve_response = self.client.post(
            f"/api/v1/borrowing/applications/{application_id}/approve/",
            {
                "action": "APPROVE",
                "opinion": "同意借阅。",
            },
            format="json",
        )

        self.assertEqual(approve_response.status_code, 200)
        self.assertEqual(approve_response.json()["data"]["status"], "APPROVED")
        self.assert_notification_exists(
            user=self.borrower_user,
            notification_type=NotificationType.BORROW_APPROVAL,
            title="档案借阅审批已通过",
            biz_id=application_id,
        )

        self.client.force_authenticate(self.archivist_user)
        checkout_response = self.client.post(
            f"/api/v1/borrowing/applications/{application_id}/checkout/",
            {
                "checkout_note": "线下完成签收。",
            },
            format="json",
        )

        self.assertEqual(checkout_response.status_code, 200)
        self.assertEqual(checkout_response.json()["data"]["status"], "CHECKED_OUT")
        archive.refresh_from_db()
        self.assertEqual(archive.status, ArchiveStatus.BORROWED)
        self.assertEqual(archive.current_borrow_id, application_id)

        self.client.force_authenticate(self.borrower_user)
        submit_return_response = self.client.post(
            f"/api/v1/borrowing/applications/{application_id}/submit-return/",
            {
                "handover_note": "交接完成，随档返还。",
                "photo_files": [
                    SimpleUploadedFile("return-photo.jpg", b"fake-image-content", content_type="image/jpeg")
                ],
            },
        )

        self.assertEqual(submit_return_response.status_code, 200)
        self.assertEqual(submit_return_response.json()["data"]["return_record"]["return_status"], "SUBMITTED")
        self.assertEqual(len(submit_return_response.json()["data"]["return_record"]["attachments"]), 1)
        self.assertEqual(
            SystemNotification.objects.filter(
                user=self.archivist_user,
                notification_type=NotificationType.RETURN_CONFIRM,
                biz_type="borrow_application",
                biz_id=application_id,
            ).count(),
            1,
        )
        self.assertEqual(
            SystemNotification.objects.filter(
                user=self.admin_user,
                notification_type=NotificationType.RETURN_CONFIRM,
                biz_type="borrow_application",
                biz_id=application_id,
            ).count(),
            1,
        )

        self.client.force_authenticate(self.archivist_user)
        confirm_response = self.client.post(
            f"/api/v1/borrowing/applications/{application_id}/confirm-return/",
            {
                "approved": True,
                "location_after_return_id": self.location.id,
                "confirm_note": "验收通过，重新上架。",
            },
            format="json",
        )

        self.assertEqual(confirm_response.status_code, 200)
        self.assertEqual(confirm_response.json()["data"]["status"], "RETURNED")
        self.assertEqual(confirm_response.json()["data"]["return_record"]["return_status"], "CONFIRMED")
        archive.refresh_from_db()
        self.assertEqual(archive.status, ArchiveStatus.ON_SHELF)
        self.assertIsNone(archive.current_borrow_id)
        self.assert_notification_exists(
            user=self.borrower_user,
            notification_type=NotificationType.RETURN_CONFIRM,
            title="档案归还已确认入库",
            biz_id=application_id,
        )

    def test_borrow_application_reject_should_notify_applicant(self) -> None:
        archive = self.create_archive(
            archive_code="A2026-B004",
            security_level=SecurityClearance.INTERNAL,
        )
        expected_return_at = (timezone.now() + timedelta(days=4)).isoformat()

        self.client.force_authenticate(self.borrower_user)
        create_response = self.client.post(
            "/api/v1/borrowing/applications/",
            {
                "archive_id": archive.id,
                "purpose": "审批驳回测试",
                "expected_return_at": expected_return_at,
            },
            format="json",
        )
        application_id = create_response.json()["data"]["id"]

        self.client.force_authenticate(self.approver_user)
        reject_response = self.client.post(
            f"/api/v1/borrowing/applications/{application_id}/approve/",
            {
                "action": "REJECT",
                "opinion": "借阅用途说明不完整。",
            },
            format="json",
        )

        self.assertEqual(reject_response.status_code, 200)
        self.assertEqual(reject_response.json()["data"]["status"], "REJECTED")
        notification = self.assert_notification_exists(
            user=self.borrower_user,
            notification_type=NotificationType.BORROW_APPROVAL,
            title="档案借阅审批已驳回",
            biz_id=application_id,
        )
        self.assertIn("借阅用途说明不完整", notification.content)

    def test_reject_return_should_notify_applicant_and_keep_archive_borrowed(self) -> None:
        archive = self.create_archive(
            archive_code="A2026-B005",
            security_level=SecurityClearance.INTERNAL,
        )
        expected_return_at = (timezone.now() + timedelta(days=5)).isoformat()

        self.client.force_authenticate(self.borrower_user)
        create_response = self.client.post(
            "/api/v1/borrowing/applications/",
            {
                "archive_id": archive.id,
                "purpose": "归还驳回测试",
                "expected_return_at": expected_return_at,
            },
            format="json",
        )
        application_id = create_response.json()["data"]["id"]

        self.client.force_authenticate(self.approver_user)
        self.client.post(
            f"/api/v1/borrowing/applications/{application_id}/approve/",
            {
                "action": "APPROVE",
                "opinion": "同意借阅。",
            },
            format="json",
        )

        self.client.force_authenticate(self.archivist_user)
        self.client.post(
            f"/api/v1/borrowing/applications/{application_id}/checkout/",
            {
                "checkout_note": "线下完成签收。",
            },
            format="json",
        )

        self.client.force_authenticate(self.borrower_user)
        submit_return_response = self.client.post(
            f"/api/v1/borrowing/applications/{application_id}/submit-return/",
            {
                "handover_note": "交接完成，待验收。",
                "photo_files": [
                    SimpleUploadedFile("return-photo.jpg", b"fake-image-content", content_type="image/jpeg")
                ],
            },
        )
        self.assertEqual(submit_return_response.status_code, 200)

        self.client.force_authenticate(self.archivist_user)
        reject_response = self.client.post(
            f"/api/v1/borrowing/applications/{application_id}/confirm-return/",
            {
                "approved": False,
                "confirm_note": "交接照片不清晰，请重新提交。",
            },
            format="json",
        )

        self.assertEqual(reject_response.status_code, 200)
        self.assertEqual(reject_response.json()["data"]["status"], "CHECKED_OUT")
        self.assertEqual(reject_response.json()["data"]["return_record"]["return_status"], "REJECTED")
        archive.refresh_from_db()
        self.assertEqual(archive.status, ArchiveStatus.BORROWED)
        self.assertEqual(archive.current_borrow_id, application_id)
        notification = self.assert_notification_exists(
            user=self.borrower_user,
            notification_type=NotificationType.RETURN_CONFIRM,
            title="档案归还验收未通过",
            biz_id=application_id,
        )
        self.assertIn("交接照片不清晰", notification.content)

    def test_low_clearance_user_should_not_create_borrow_application_for_high_security_archive(self) -> None:
        archive = self.create_archive(
            archive_code="A2026-B002",
            security_level=SecurityClearance.SECRET,
        )
        expected_return_at = (timezone.now() + timedelta(days=3)).isoformat()

        self.client.force_authenticate(self.borrower_user)
        response = self.client.post(
            "/api/v1/borrowing/applications/",
            {
                "archive_id": archive.id,
                "purpose": "权限测试",
                "expected_return_at": expected_return_at,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "当前账号密级不足，不能申请该档案借阅。")

    def test_submit_return_without_attachments_should_fail(self) -> None:
        archive = self.create_archive(
            archive_code="A2026-B003",
            security_level=SecurityClearance.INTERNAL,
        )
        expected_return_at = timezone.now() + timedelta(days=2)
        self.client.force_authenticate(self.admin_user)
        application = self.client.post(
            "/api/v1/borrowing/applications/",
            {
                "archive_id": archive.id,
                "purpose": "管理员代测借阅",
                "expected_return_at": expected_return_at.isoformat(),
            },
            format="json",
        ).json()["data"]

        application_id = application["id"]

        self.client.force_authenticate(self.approver_user)
        self.client.post(
            f"/api/v1/borrowing/applications/{application_id}/approve/",
            {"action": "APPROVE", "opinion": "通过"},
            format="json",
        )

        self.client.force_authenticate(self.archivist_user)
        self.client.post(
            f"/api/v1/borrowing/applications/{application_id}/checkout/",
            {"checkout_note": "准备借出"},
            format="json",
        )

        self.client.force_authenticate(self.admin_user)
        response = self.client.post(
            f"/api/v1/borrowing/applications/{application_id}/submit-return/",
            {"handover_note": "未上传附件"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "归还时至少需要上传照片或交接单中的一种。")
