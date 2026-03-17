from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import DataScope, Role, SecurityClearance, SystemPermission
from apps.accounts.services import assign_permissions_to_role, assign_roles_to_user
from apps.archives.models import ArchiveRecord, ArchiveStatus, ArchiveStorageLocation
from apps.destruction.models import DestroyApplication, DestroyApplicationStatus
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class DestructionApiTests(APITestCase):
    def setUp(self) -> None:
        self.client = APIClient()

        self.department = Department.objects.create(
            dept_code="ROOT",
            dept_name="总部",
        )
        sync_department_hierarchy(self.department)

        self.admin_role = Role.objects.create(
            role_code="ADMIN",
            role_name="管理员",
            data_scope=DataScope.ALL,
            status=True,
        )
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
        self.destroy_approve_permission = SystemPermission.objects.create(
            permission_code="button.destruction.approve",
            permission_name="审批销毁申请",
            permission_type="BUTTON",
            module_name="destruction",
            sort_order=340,
            status=True,
        )
        self.destroy_menu_permission = SystemPermission.objects.create(
            permission_code="menu.destruction_center",
            permission_name="销毁中心",
            permission_type="MENU",
            module_name="destruction",
            route_path="/destruction/applications",
            sort_order=100,
            status=True,
        )
        self.destroy_approver_role = Role.objects.create(
            role_code="DESTROY_APPROVER",
            role_name="销毁审批人",
            data_scope=DataScope.ALL,
            status=True,
        )
        assign_permissions_to_role(
            self.destroy_approver_role,
            [self.destroy_approve_permission.id, self.destroy_menu_permission.id],
        )

        self.admin_user = User.objects.create_user(
            username="destroy_admin",
            password="Admin12345",
            real_name="管理员甲",
            dept=self.department,
            email="admin@example.com",
            is_staff=True,
            security_clearance_level=SecurityClearance.SECRET,
        )
        assign_roles_to_user(self.admin_user, [self.admin_role.id])

        self.archivist_user = User.objects.create_user(
            username="destroy_archivist",
            password="Archivist123",
            real_name="档案员甲",
            dept=self.department,
            email="archivist@example.com",
            is_staff=True,
            security_clearance_level=SecurityClearance.SECRET,
        )
        assign_roles_to_user(self.archivist_user, [self.archivist_role.id])

        self.borrower_user = User.objects.create_user(
            username="destroy_borrower",
            password="Borrower12345",
            real_name="借阅人甲",
            dept=self.department,
            email="borrower@example.com",
            security_clearance_level=SecurityClearance.INTERNAL,
        )
        assign_roles_to_user(self.borrower_user, [self.borrower_role.id])
        self.destroy_approver_user = User.objects.create_user(
            username="destroy_approver",
            password="DestroyApprover123",
            real_name="销毁审批人甲",
            dept=self.department,
            email="destroy-approver@example.com",
            is_staff=True,
            security_clearance_level=SecurityClearance.SECRET,
        )
        assign_roles_to_user(self.destroy_approver_user, [self.destroy_approver_role.id])

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

    def create_archive(self, *, archive_code: str, status: str = ArchiveStatus.ON_SHELF) -> ArchiveRecord:
        return ArchiveRecord.objects.create(
            archive_code=archive_code,
            title=f"{archive_code} 档案",
            year=2026,
            retention_period="长期",
            security_level=SecurityClearance.INTERNAL,
            status=status,
            responsible_dept=self.department,
            location=self.location,
            created_by=self.archivist_user.id,
            updated_by=self.archivist_user.id,
        )

    def create_destroy_application(self, archive: ArchiveRecord) -> int:
        self.client.force_authenticate(self.archivist_user)
        response = self.client.post(
            "/api/v1/destruction/applications/",
            {
                "archive_id": archive.id,
                "reason": "保管期限届满且无继续保存价值",
                "basis": "档案销毁管理制度第八条",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return response.json()["data"]["id"]

    def test_archivist_can_create_destroy_application(self) -> None:
        archive = self.create_archive(archive_code="A2026-D001")

        application_id = self.create_destroy_application(archive)

        application = DestroyApplication.objects.get(id=application_id)
        archive.refresh_from_db()

        self.assertEqual(application.status, DestroyApplicationStatus.PENDING_APPROVAL)
        self.assertEqual(application.current_approver_id, self.admin_user.id)
        self.assertEqual(archive.status, ArchiveStatus.DESTROY_PENDING)

        self.client.force_authenticate(self.admin_user)
        approval_list = self.client.get("/api/v1/destruction/applications/?scope=approval")
        notification_list = self.client.get("/api/v1/notifications/messages/")

        self.assertEqual(approval_list.status_code, 200)
        self.assertEqual(len(approval_list.json()["data"]), 1)
        self.assertEqual(notification_list.status_code, 200)
        self.assertEqual(len(notification_list.json()["data"]), 1)
        self.assertEqual(notification_list.json()["data"][0]["notification_type"], "DESTROY_APPROVAL")

    def test_admin_can_approve_and_archivist_can_execute_destroy_application(self) -> None:
        archive = self.create_archive(archive_code="A2026-D002")
        application_id = self.create_destroy_application(archive)

        self.client.force_authenticate(self.admin_user)
        approve_response = self.client.post(
            f"/api/v1/destruction/applications/{application_id}/approve/",
            {
                "action": "APPROVE",
                "opinion": "符合制度要求",
            },
            format="json",
        )
        self.assertEqual(approve_response.status_code, 200)

        application = DestroyApplication.objects.get(id=application_id)
        self.assertEqual(application.status, DestroyApplicationStatus.APPROVED)

        self.client.force_authenticate(self.archivist_user)
        execute_response = self.client.post(
            f"/api/v1/destruction/applications/{application_id}/execute/",
            {
                "execution_note": "已完成纸质档案销毁并登记台账",
                "attachment_files": [
                    SimpleUploadedFile("destroy-proof.pdf", b"proof-content", content_type="application/pdf")
                ],
            },
            format="multipart",
        )

        self.assertEqual(execute_response.status_code, 200)
        application.refresh_from_db()
        archive.refresh_from_db()

        self.assertEqual(application.status, DestroyApplicationStatus.EXECUTED)
        self.assertEqual(archive.status, ArchiveStatus.DESTROYED)
        self.assertIsNotNone(application.executed_at)
        self.assertEqual(application.execution_record.attachments.count(), 1)

        detail_response = self.client.get(f"/api/v1/destruction/applications/{application_id}/")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["data"]["execution_record"]["attachments"][0]["file_name"], "destroy-proof.pdf")

    def test_reject_should_restore_archive_to_on_shelf(self) -> None:
        archive = self.create_archive(archive_code="A2026-D003")
        application_id = self.create_destroy_application(archive)

        self.client.force_authenticate(self.admin_user)
        response = self.client.post(
            f"/api/v1/destruction/applications/{application_id}/approve/",
            {
                "action": "REJECT",
                "opinion": "销毁依据不足，需要补充审签材料",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        application = DestroyApplication.objects.get(id=application_id)
        archive.refresh_from_db()

        self.assertEqual(application.status, DestroyApplicationStatus.REJECTED)
        self.assertEqual(application.reject_reason, "销毁依据不足，需要补充审签材料")
        self.assertEqual(archive.status, ArchiveStatus.ON_SHELF)

    def test_borrowed_archive_should_not_allow_create_destroy_application(self) -> None:
        archive = self.create_archive(archive_code="A2026-D004", status=ArchiveStatus.BORROWED)

        self.client.force_authenticate(self.archivist_user)
        response = self.client.post(
            "/api/v1/destruction/applications/",
            {
                "archive_id": archive.id,
                "reason": "借出中测试",
                "basis": "制度条款",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(DestroyApplication.objects.count(), 0)

    def test_borrower_should_not_allow_create_destroy_application(self) -> None:
        archive = self.create_archive(archive_code="A2026-D005")

        self.client.force_authenticate(self.borrower_user)
        response = self.client.post(
            "/api/v1/destruction/applications/",
            {
                "archive_id": archive.id,
                "reason": "越权创建测试",
                "basis": "制度条款",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(DestroyApplication.objects.count(), 0)

    def test_archivist_should_not_approve_destroy_application(self) -> None:
        archive = self.create_archive(archive_code="A2026-D006")
        application_id = self.create_destroy_application(archive)

        self.client.force_authenticate(self.archivist_user)
        response = self.client.post(
            f"/api/v1/destruction/applications/{application_id}/approve/",
            {
                "action": "APPROVE",
                "opinion": "越权审批测试",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        application = DestroyApplication.objects.get(id=application_id)
        self.assertEqual(application.status, DestroyApplicationStatus.PENDING_APPROVAL)

    def test_reject_without_opinion_should_fail_validation(self) -> None:
        archive = self.create_archive(archive_code="A2026-D007")
        application_id = self.create_destroy_application(archive)

        self.client.force_authenticate(self.admin_user)
        response = self.client.post(
            f"/api/v1/destruction/applications/{application_id}/approve/",
            {
                "action": "REJECT",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        application = DestroyApplication.objects.get(id=application_id)
        archive.refresh_from_db()

        self.assertEqual(application.status, DestroyApplicationStatus.PENDING_APPROVAL)
        self.assertEqual(application.approval_records.count(), 0)
        self.assertEqual(archive.status, ArchiveStatus.DESTROY_PENDING)

    @override_settings(ARCHIVE_UPLOAD_MAX_SIZE_MB=1)
    def test_execute_should_reject_invalid_attachment_extension_and_keep_state(self) -> None:
        archive = self.create_archive(archive_code="A2026-D008")
        application_id = self.create_destroy_application(archive)

        self.client.force_authenticate(self.admin_user)
        approve_response = self.client.post(
            f"/api/v1/destruction/applications/{application_id}/approve/",
            {
                "action": "APPROVE",
                "opinion": "允许执行",
            },
            format="json",
        )
        self.assertEqual(approve_response.status_code, 200)

        self.client.force_authenticate(self.archivist_user)
        execute_response = self.client.post(
            f"/api/v1/destruction/applications/{application_id}/execute/",
            {
                "execution_note": "非法附件测试",
                "attachment_files": [
                    SimpleUploadedFile("destroy-proof.exe", b"proof-content", content_type="application/octet-stream")
                ],
            },
            format="multipart",
        )

        self.assertEqual(execute_response.status_code, 400)
        self.assertIn("不支持的销毁附件格式", str(execute_response.json()))

        application = DestroyApplication.objects.get(id=application_id)
        archive.refresh_from_db()
        self.assertEqual(application.status, DestroyApplicationStatus.APPROVED)
        self.assertFalse(hasattr(application, "execution_record"))
        self.assertEqual(archive.status, ArchiveStatus.DESTROY_PENDING)

    def test_user_with_destroy_approve_permission_should_view_and_approve_assigned_application(self) -> None:
        archive = self.create_archive(archive_code="A2026-D099")
        application_id = self.create_destroy_application(archive)
        application = DestroyApplication.objects.get(id=application_id)
        application.current_approver = self.destroy_approver_user
        application.save(update_fields=["current_approver_id", "updated_at"])

        self.client.force_authenticate(self.destroy_approver_user)
        approval_list = self.client.get("/api/v1/destruction/applications/?scope=approval")
        approve_response = self.client.post(
            f"/api/v1/destruction/applications/{application_id}/approve/",
            {
                "action": "APPROVE",
                "opinion": "按权限分配完成审批。",
            },
            format="json",
        )

        self.assertEqual(approval_list.status_code, 200)
        self.assertEqual(len(approval_list.json()["data"]), 1)
        self.assertEqual(approve_response.status_code, 200)
        application.refresh_from_db()
        self.assertEqual(application.status, DestroyApplicationStatus.APPROVED)

    def test_execute_destroy_application_should_reject_duplicate_execution(self) -> None:
        archive = self.create_archive(archive_code="A2026-D100")
        application_id = self.create_destroy_application(archive)

        self.client.force_authenticate(self.admin_user)
        approve_response = self.client.post(
            f"/api/v1/destruction/applications/{application_id}/approve/",
            {
                "action": "APPROVE",
                "opinion": "允许执行",
            },
            format="json",
        )
        self.assertEqual(approve_response.status_code, 200)

        self.client.force_authenticate(self.archivist_user)
        first_execute_response = self.client.post(
            f"/api/v1/destruction/applications/{application_id}/execute/",
            {
                "execution_note": "首次执行销毁",
                "attachment_files": [
                    SimpleUploadedFile("destroy-proof.pdf", b"proof-content", content_type="application/pdf")
                ],
            },
            format="multipart",
        )
        second_execute_response = self.client.post(
            f"/api/v1/destruction/applications/{application_id}/execute/",
            {
                "execution_note": "重复执行销毁",
                "attachment_files": [
                    SimpleUploadedFile("destroy-proof-2.pdf", b"proof-content-2", content_type="application/pdf")
                ],
            },
            format="multipart",
        )

        self.assertEqual(first_execute_response.status_code, 200)
        self.assertEqual(second_execute_response.status_code, 400)
        self.assertEqual(second_execute_response.json()["message"], "当前销毁申请已完成执行，不能重复处理。")
