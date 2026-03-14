from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError

from apps.accounts.models import SecurityClearance
from apps.archives.models import ArchiveRecord, ArchiveStatus, ArchiveStorageLocation
from apps.digitization.models import ScanTask, ScanTaskItem, ScanTaskItemStatus, ScanTaskStatus
from apps.digitization.services import sync_scan_task_counters, validate_scan_task_archives, validate_uploaded_file
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class DigitizationServicesUnitTests(TestCase):
    def setUp(self) -> None:
        self.department = Department.objects.create(
            dept_code="UNIT_SCAN",
            dept_name="扫描单元测试部",
        )
        sync_department_hierarchy(self.department)

        self.operator = User.objects.create_user(
            username="scan_unit_user",
            password="ScanUnit12345",
            real_name="扫描单元测试用户",
            dept=self.department,
            security_clearance_level=SecurityClearance.SECRET,
            status=True,
        )

        self.location = ArchiveStorageLocation.objects.create(
            warehouse_name="三号库房",
            area_name="C区",
            cabinet_code="G03",
            rack_code="J03",
            layer_code="L03",
            box_code="H03",
            status=True,
            created_by=self.operator.id,
            updated_by=self.operator.id,
        )

    def create_archive(self, *, archive_code: str, status: str) -> ArchiveRecord:
        return ArchiveRecord.objects.create(
            archive_code=archive_code,
            title=f"{archive_code} 扫描测试档案",
            year=2026,
            retention_period="长期",
            security_level=SecurityClearance.INTERNAL,
            status=status,
            responsible_dept=self.department,
            responsible_person="责任人丙",
            summary="扫描服务层单元测试数据。",
            location=self.location,
            created_by=self.operator.id,
            updated_by=self.operator.id,
        )

    def test_validate_scan_task_archives_should_raise_when_archive_list_is_empty(self) -> None:
        with self.assertRaisesMessage(ValidationError, "扫描任务至少需要选择一份档案。"):
            validate_scan_task_archives([])

    def test_validate_scan_task_archives_should_raise_when_archive_status_is_invalid(self) -> None:
        invalid_archive = self.create_archive(
            archive_code="A2026-DU001",
            status=ArchiveStatus.ON_SHELF,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "以下档案当前状态不允许创建扫描任务：A2026-DU001。",
        ):
            validate_scan_task_archives([invalid_archive])

    def test_sync_scan_task_counters_should_mark_task_completed_when_all_items_complete(self) -> None:
        archive_one = self.create_archive(archive_code="A2026-DU002", status=ArchiveStatus.DRAFT)
        archive_two = self.create_archive(archive_code="A2026-DU003", status=ArchiveStatus.DRAFT)
        task = ScanTask.objects.create(
            task_no="SCANUNIT0001",
            task_name="扫描单元测试任务",
            assigned_user_id=self.operator.id,
            assigned_by=self.operator.id,
            created_by=self.operator.id,
            updated_by=self.operator.id,
        )
        ScanTaskItem.objects.create(
            task=task,
            archive=archive_one,
            assignee_user_id=self.operator.id,
            status=ScanTaskItemStatus.COMPLETED,
        )
        ScanTaskItem.objects.create(
            task=task,
            archive=archive_two,
            assignee_user_id=self.operator.id,
            status=ScanTaskItemStatus.COMPLETED,
        )

        synced_task = sync_scan_task_counters(task)

        synced_task.refresh_from_db()
        self.assertEqual(synced_task.total_count, 2)
        self.assertEqual(synced_task.completed_count, 2)
        self.assertEqual(synced_task.failed_count, 0)
        self.assertEqual(synced_task.status, ScanTaskStatus.COMPLETED)
        self.assertIsNotNone(synced_task.started_at)
        self.assertIsNotNone(synced_task.finished_at)

    @override_settings(ARCHIVE_UPLOAD_MAX_SIZE_MB=1)
    def test_validate_uploaded_file_should_reject_invalid_extension(self) -> None:
        invalid_file = SimpleUploadedFile("malware.exe", b"1234", content_type="application/octet-stream")

        with self.assertRaisesMessage(ValidationError, "不支持的文件格式：exe。"):
            validate_uploaded_file(invalid_file)

    @override_settings(ARCHIVE_UPLOAD_MAX_SIZE_MB=1)
    def test_validate_uploaded_file_should_reject_oversize_file(self) -> None:
        oversized_file = SimpleUploadedFile(
            "large.pdf",
            b"x" * (1024 * 1024 + 1),
            content_type="application/pdf",
        )

        with self.assertRaisesMessage(ValidationError, "单个文件大小不能超过 1 MB。"):
            validate_uploaded_file(oversized_file)
