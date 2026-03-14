from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from apps.accounts.models import SecurityClearance
from apps.archives.models import ArchiveBarcode, ArchiveCodeType, ArchiveRecord, ArchiveStatus, ArchiveStorageLocation
from apps.archives.services import (
    ARCHIVE_SNAPSHOT_FIELDS,
    batch_print_archive_codes,
    build_archive_changes,
    transition_archive_status,
    user_can_view_archive_sensitive_fields,
)
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class ArchiveServicesUnitTests(TestCase):
    def setUp(self) -> None:
        self.department = Department.objects.create(
            dept_code="UNIT_ARCH",
            dept_name="档案单元测试部",
        )
        sync_department_hierarchy(self.department)

        self.operator = User.objects.create_user(
            username="archive_operator",
            password="Archive12345",
            real_name="档案操作员",
            dept=self.department,
            security_clearance_level=SecurityClearance.TOP_SECRET,
            status=True,
        )
        self.low_clearance_user = User.objects.create_user(
            username="archive_low",
            password="ArchiveLow12345",
            real_name="低密级用户",
            dept=self.department,
            security_clearance_level=SecurityClearance.INTERNAL,
            status=True,
        )
        self.high_clearance_user = User.objects.create_user(
            username="archive_high",
            password="ArchiveHigh12345",
            real_name="高密级用户",
            dept=self.department,
            security_clearance_level=SecurityClearance.SECRET,
            status=True,
        )

        self.location = ArchiveStorageLocation.objects.create(
            warehouse_name="一号库房",
            area_name="A区",
            cabinet_code="G01",
            rack_code="J01",
            layer_code="L01",
            box_code="H01",
            status=True,
            created_by=self.operator.id,
            updated_by=self.operator.id,
        )

    def create_archive(self, *, archive_code: str, status: str, security_level: str) -> ArchiveRecord:
        return ArchiveRecord.objects.create(
            archive_code=archive_code,
            title=f"{archive_code} 测试档案",
            year=2026,
            retention_period="长期",
            security_level=security_level,
            status=status,
            responsible_dept=self.department,
            responsible_person="责任人甲",
            summary="用于服务层单元测试。",
            location=self.location,
            created_by=self.operator.id,
            updated_by=self.operator.id,
        )

    def test_build_archive_changes_should_only_keep_changed_fields(self) -> None:
        before_snapshot = {field_name: None for field_name in ARCHIVE_SNAPSHOT_FIELDS}
        before_snapshot["title"] = "旧题名"
        before_snapshot["page_count"] = 12
        before_snapshot["status"] = ArchiveStatus.DRAFT

        after_snapshot = before_snapshot.copy()
        after_snapshot["title"] = "新题名"
        after_snapshot["page_count"] = 24

        changed_fields = build_archive_changes(before_snapshot, after_snapshot)

        self.assertEqual(set(changed_fields.keys()), {"title", "page_count"})
        self.assertEqual(changed_fields["title"]["before"], "旧题名")
        self.assertEqual(changed_fields["title"]["after"], "新题名")

    def test_transition_archive_status_should_require_current_borrow_id_when_target_is_borrowed(self) -> None:
        archive = self.create_archive(
            archive_code="A2026-U001",
            status=ArchiveStatus.ON_SHELF,
            security_level=SecurityClearance.INTERNAL,
        )

        with self.assertRaisesMessage(ValidationError, "流转到借出中状态时必须提供当前借阅单 ID。"):
            transition_archive_status(
                archive=archive,
                next_status=ArchiveStatus.BORROWED,
                operator_id=self.operator.id,
            )

    def test_transition_archive_status_should_set_shelved_fields_when_move_to_on_shelf(self) -> None:
        archive = self.create_archive(
            archive_code="A2026-U002",
            status=ArchiveStatus.PENDING_CATALOG,
            security_level=SecurityClearance.INTERNAL,
        )

        transitioned_archive = transition_archive_status(
            archive=archive,
            next_status=ArchiveStatus.ON_SHELF,
            operator_id=self.operator.id,
            remark="单元测试流转上架",
        )

        transitioned_archive.refresh_from_db()
        self.assertEqual(transitioned_archive.status, ArchiveStatus.ON_SHELF)
        self.assertIsNotNone(transitioned_archive.catalog_completed_at)
        self.assertIsNotNone(transitioned_archive.shelved_at)
        self.assertEqual(transitioned_archive.revisions.count(), 1)

    def test_batch_print_archive_codes_should_reject_when_any_archive_missing_codes(self) -> None:
        ready_archive = self.create_archive(
            archive_code="A2026-U004",
            status=ArchiveStatus.ON_SHELF,
            security_level=SecurityClearance.INTERNAL,
        )
        pending_archive = self.create_archive(
            archive_code="A2026-U005",
            status=ArchiveStatus.ON_SHELF,
            security_level=SecurityClearance.INTERNAL,
        )
        ArchiveBarcode.objects.create(
            archive=ready_archive,
            code_type=ArchiveCodeType.BARCODE,
            code_content=ready_archive.archive_code,
            image_path="barcodes/test-ready.png",
            created_by=self.operator.id,
        )

        with self.assertRaisesMessage(ValidationError, "以下档案尚未生成条码或二维码：A2026-U005。"):
            batch_print_archive_codes(
                archive_ids=[ready_archive.id, pending_archive.id],
                operator_id=self.operator.id,
            )

        ready_archive.refresh_from_db()
        self.assertEqual(ready_archive.barcodes.first().print_count, 0)

    def test_user_can_view_archive_sensitive_fields_should_compare_security_clearance(self) -> None:
        archive = self.create_archive(
            archive_code="A2026-U003",
            status=ArchiveStatus.ON_SHELF,
            security_level=SecurityClearance.SECRET,
        )

        self.assertFalse(user_can_view_archive_sensitive_fields(self.low_clearance_user, archive))
        self.assertTrue(user_can_view_archive_sensitive_fields(self.high_clearance_user, archive))
