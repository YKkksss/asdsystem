from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError

from apps.accounts.models import DataScope, Role, SecurityClearance
from apps.accounts.services import assign_roles_to_user
from apps.archives.models import ArchiveRecord, ArchiveStatus, ArchiveStorageLocation
from apps.destruction.models import DestroyApprovalAction, DestroyExecutionRecord
from apps.destruction.services import (
    approve_destroy_application,
    can_user_approve_destroy_application,
    can_user_execute_destroy_application,
    create_destroy_application,
    execute_destroy_application,
    validate_destroy_attachment,
)
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class DestructionServicesUnitTests(TestCase):
    def setUp(self) -> None:
        self.department = Department.objects.create(
            dept_code="UNIT_DESTROY",
            dept_name="销毁单元测试部",
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

        self.admin_user = User.objects.create_user(
            username="destroy_unit_admin",
            password="Admin12345",
            real_name="销毁单元测试管理员",
            dept=self.department,
            email="destroy-unit-admin@example.com",
            status=True,
            is_staff=True,
            security_clearance_level=SecurityClearance.SECRET,
        )
        assign_roles_to_user(self.admin_user, [self.admin_role.id])

        self.archivist_user = User.objects.create_user(
            username="destroy_unit_archivist",
            password="Archivist12345",
            real_name="销毁单元测试档案员",
            dept=self.department,
            email="destroy-unit-archivist@example.com",
            status=True,
            is_staff=True,
            security_clearance_level=SecurityClearance.SECRET,
        )
        assign_roles_to_user(self.archivist_user, [self.archivist_role.id])

        self.borrower_user = User.objects.create_user(
            username="destroy_unit_borrower",
            password="Borrower12345",
            real_name="销毁单元测试借阅人",
            dept=self.department,
            email="destroy-unit-borrower@example.com",
            status=True,
            security_clearance_level=SecurityClearance.INTERNAL,
        )
        assign_roles_to_user(self.borrower_user, [self.borrower_role.id])

        self.location = ArchiveStorageLocation.objects.create(
            warehouse_name="三号库房",
            area_name="C区",
            cabinet_code="G03",
            rack_code="J03",
            layer_code="L03",
            box_code="H03",
            status=True,
            created_by=self.archivist_user.id,
            updated_by=self.archivist_user.id,
        )

    def create_archive(self, *, archive_code: str, status: str = ArchiveStatus.ON_SHELF) -> ArchiveRecord:
        return ArchiveRecord.objects.create(
            archive_code=archive_code,
            title=f"{archive_code} 销毁测试档案",
            year=2026,
            retention_period="长期",
            security_level=SecurityClearance.INTERNAL,
            status=status,
            responsible_dept=self.department,
            responsible_person="责任人丙",
            summary="销毁服务层单元测试数据。",
            location=self.location,
            created_by=self.archivist_user.id,
            updated_by=self.archivist_user.id,
        )

    def test_create_destroy_application_should_reject_user_without_archive_role(self) -> None:
        archive = self.create_archive(archive_code="A2026-DU001")

        with self.assertRaisesMessage(ValidationError, "当前用户缺少发起销毁申请的权限。"):
            create_destroy_application(
                archive=archive,
                reason="权限校验测试",
                basis="制度条款",
                operator=self.borrower_user,
            )

        archive.refresh_from_db()
        self.assertEqual(archive.status, ArchiveStatus.ON_SHELF)

    def test_validate_destroy_attachment_should_reject_invalid_extension(self) -> None:
        invalid_file = SimpleUploadedFile("destroy-proof.exe", b"bad-file", content_type="application/octet-stream")

        with self.assertRaisesMessage(ValidationError, "不支持的销毁附件格式：exe。"):
            validate_destroy_attachment(invalid_file)

    @override_settings(ARCHIVE_UPLOAD_MAX_SIZE_MB=1)
    def test_validate_destroy_attachment_should_reject_oversize_file(self) -> None:
        oversize_file = SimpleUploadedFile(
            "destroy-proof.pdf",
            b"x" * (1024 * 1024 + 1),
            content_type="application/pdf",
        )

        with self.assertRaisesMessage(ValidationError, "单个销毁附件大小不能超过 1 MB。"):
            validate_destroy_attachment(oversize_file)

    def test_permission_helpers_should_match_role_and_status_constraints(self) -> None:
        archive = self.create_archive(archive_code="A2026-DU002")
        application = create_destroy_application(
            archive=archive,
            reason="权限判断测试",
            basis="制度条款",
            operator=self.archivist_user,
        )

        self.assertTrue(can_user_approve_destroy_application(self.admin_user, application))
        self.assertFalse(can_user_approve_destroy_application(self.archivist_user, application))
        self.assertFalse(can_user_execute_destroy_application(self.archivist_user, application))

        approved_application = approve_destroy_application(
            application=application,
            approver=self.admin_user,
            action=DestroyApprovalAction.APPROVE,
            opinion="同意执行",
        )

        self.assertTrue(can_user_execute_destroy_application(self.archivist_user, approved_application))
        self.assertTrue(can_user_execute_destroy_application(self.admin_user, approved_application))
        self.assertFalse(can_user_execute_destroy_application(self.borrower_user, approved_application))

    def test_execute_destroy_application_should_reject_when_archive_not_destroy_pending(self) -> None:
        archive = self.create_archive(archive_code="A2026-DU003")
        application = create_destroy_application(
            archive=archive,
            reason="执行前校验测试",
            basis="制度条款",
            operator=self.archivist_user,
        )
        approved_application = approve_destroy_application(
            application=application,
            approver=self.admin_user,
            action=DestroyApprovalAction.APPROVE,
            opinion="可以执行",
        )

        archive.status = ArchiveStatus.ON_SHELF
        archive.save(update_fields=["status", "updated_at"])

        with self.assertRaisesMessage(ValidationError, "当前档案不在待销毁状态，不能执行销毁。"):
            execute_destroy_application(
                application=approved_application,
                operator=self.archivist_user,
                execution_note="执行说明",
                attachment_files=[],
            )

        approved_application.refresh_from_db()
        archive.refresh_from_db()
        self.assertEqual(approved_application.status, "APPROVED")
        self.assertEqual(archive.status, ArchiveStatus.ON_SHELF)
        self.assertEqual(DestroyExecutionRecord.objects.count(), 0)
