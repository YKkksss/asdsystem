import io
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import fitz
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import DataScope, Role, SecurityClearance, SystemPermission
from apps.accounts.services import assign_permissions_to_role, assign_roles_to_user
from apps.archives.models import ArchiveFile, ArchiveFileStatus, ArchiveStatus
from apps.digitization.services import process_file_process_job
from apps.digitization.models import FileProcessJob, FileProcessJobStatus, ScanTaskItemStatus, ScanTaskStatus
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class ScanTaskApiTests(APITestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root, CELERY_TASK_ALWAYS_EAGER=True)
        self.override.enable()

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
        self.scan_menu_permission = SystemPermission.objects.create(
            permission_code="menu.scan_task",
            permission_name="数字化任务",
            permission_type="MENU",
            module_name="digitization",
            route_path="/digitization/scan-tasks",
            sort_order=40,
            status=True,
        )
        self.scan_manage_permission = SystemPermission.objects.create(
            permission_code="button.scan_task.manage",
            permission_name="维护数字化任务",
            permission_type="BUTTON",
            module_name="digitization",
            sort_order=270,
            status=True,
        )
        self.scan_operator_role = Role.objects.create(
            role_code="SCAN_OPERATOR",
            role_name="数字化操作员",
            data_scope=DataScope.DEPT,
            status=True,
        )
        assign_permissions_to_role(
            self.scan_operator_role,
            [self.scan_menu_permission.id, self.scan_manage_permission.id],
        )
        self.user = User.objects.create_user(
            username="archivist",
            password="Archivist123",
            real_name="档案员甲",
            dept=self.department,
            is_staff=True,
        )
        assign_roles_to_user(self.user, [self.archivist_role.id])
        self.scan_operator_user = User.objects.create_user(
            username="scan_operator",
            password="ScanOperator123",
            real_name="数字化操作员",
            dept=self.department,
            is_staff=True,
        )
        assign_roles_to_user(self.scan_operator_user, [self.scan_operator_role.id])
        self.client.force_authenticate(self.user)

    def tearDown(self) -> None:
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    def _create_archive(self, archive_code: str):
        from apps.archives.models import ArchiveRecord

        return ArchiveRecord.objects.create(
            archive_code=archive_code,
            title=f"{archive_code} 档案",
            year=2026,
            retention_period="长期",
            security_level=SecurityClearance.INTERNAL,
            status=ArchiveStatus.DRAFT,
            created_by=self.user.id,
            updated_by=self.user.id,
        )

    def _create_pdf_file(self) -> SimpleUploadedFile:
        document = fitz.open()
        page = document.new_page()
        page.insert_text((72, 72), "Scan Task PDF Text Extraction")
        pdf_bytes = document.tobytes()
        document.close()
        return SimpleUploadedFile("scan-test.pdf", pdf_bytes, content_type="application/pdf")

    def test_create_scan_task_should_create_items_and_move_archives_to_pending_scan(self) -> None:
        archive_a = self._create_archive("SCAN-2026-001")
        archive_b = self._create_archive("SCAN-2026-002")

        response = self.client.post(
            "/api/v1/digitization/scan-tasks/",
            {
                "task_name": "第一批扫描任务",
                "archive_ids": [archive_a.id, archive_b.id],
                "remark": "批量数字化",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["total_count"], 2)
        self.assertEqual(len(response.json()["data"]["items"]), 2)

        archive_a.refresh_from_db()
        archive_b.refresh_from_db()
        self.assertEqual(archive_a.status, ArchiveStatus.PENDING_SCAN)
        self.assertEqual(archive_b.status, ArchiveStatus.PENDING_SCAN)

    def test_upload_pdf_should_create_archive_file_thumbnail_and_extracted_text(self) -> None:
        archive = self._create_archive("SCAN-2026-003")
        create_response = self.client.post(
            "/api/v1/digitization/scan-tasks/",
            {
                "task_name": "PDF 上传任务",
                "archive_ids": [archive.id],
            },
            format="json",
        )
        task_item_id = create_response.json()["data"]["items"][0]["id"]

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/v1/digitization/scan-task-items/{task_item_id}/upload-files/",
                {"files": [self._create_pdf_file()]},
                format="multipart",
            )

        self.assertEqual(response.status_code, 200)

        archive.refresh_from_db()
        self.assertEqual(archive.status, ArchiveStatus.PENDING_CATALOG)

        archive_file = ArchiveFile.objects.filter(archive=archive).first()
        self.assertIsNotNone(archive_file)
        self.assertEqual(archive_file.status, ArchiveFileStatus.ACTIVE)
        self.assertTrue(archive_file.thumbnail_path)
        self.assertTrue(Path(self.media_root, archive_file.file_path).exists())
        self.assertTrue(Path(self.media_root, archive_file.thumbnail_path).exists())
        self.assertIn("Scan Task PDF Text Extraction", archive_file.extracted_text or "")

        jobs = FileProcessJob.objects.filter(archive_file=archive_file)
        self.assertEqual(jobs.count(), 2)
        self.assertFalse(jobs.exclude(status=FileProcessJobStatus.SUCCESS).exists())

        task_detail_response = self.client.get(f"/api/v1/digitization/scan-tasks/{create_response.json()['data']['id']}/")
        self.assertEqual(task_detail_response.status_code, 200)
        self.assertEqual(task_detail_response.json()["data"]["status"], ScanTaskStatus.COMPLETED)
        self.assertEqual(task_detail_response.json()["data"]["completed_count"], 1)
        self.assertEqual(task_detail_response.json()["data"]["items"][0]["uploaded_file_count"], 1)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch("apps.digitization.services.process_file_process_job_task.delay")
    def test_upload_pdf_should_dispatch_jobs_after_transaction_commit(self, mocked_delay) -> None:
        archive = self._create_archive("SCAN-2026-006")
        create_response = self.client.post(
            "/api/v1/digitization/scan-tasks/",
            {
                "task_name": "异步上传任务",
                "archive_ids": [archive.id],
            },
            format="json",
        )
        task_item_id = create_response.json()["data"]["items"][0]["id"]

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            response = self.client.post(
                f"/api/v1/digitization/scan-task-items/{task_item_id}/upload-files/",
                {"files": [self._create_pdf_file()]},
                format="multipart",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], ScanTaskStatus.IN_PROGRESS)
        self.assertEqual(response.json()["data"]["items"][0]["status"], ScanTaskItemStatus.PROCESSING)
        self.assertEqual(mocked_delay.call_count, 0)
        self.assertEqual(len(callbacks), 1)

        archive_file = ArchiveFile.objects.get(scan_task_item_id=task_item_id)
        jobs = FileProcessJob.objects.filter(archive_file=archive_file)
        self.assertEqual(jobs.count(), 2)
        self.assertFalse(jobs.exclude(status=FileProcessJobStatus.PENDING).exists())

        callbacks[0]()
        self.assertEqual(mocked_delay.call_count, 2)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch("apps.digitization.services.process_file_process_job_task.delay")
    def test_non_eager_upload_should_allow_jobs_process_from_pending_to_success(self, mocked_delay) -> None:
        archive = self._create_archive("SCAN-2026-006A")
        create_response = self.client.post(
            "/api/v1/digitization/scan-tasks/",
            {
                "task_name": "异步处理收口测试",
                "archive_ids": [archive.id],
            },
            format="json",
        )
        task_id = create_response.json()["data"]["id"]
        task_item_id = create_response.json()["data"]["items"][0]["id"]

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            upload_response = self.client.post(
                f"/api/v1/digitization/scan-task-items/{task_item_id}/upload-files/",
                {"files": [self._create_pdf_file()]},
                format="multipart",
            )

        self.assertEqual(upload_response.status_code, 200)

        archive_file = ArchiveFile.objects.get(scan_task_item_id=task_item_id)
        jobs = list(FileProcessJob.objects.filter(archive_file=archive_file).order_by("id"))
        self.assertEqual(len(jobs), 2)
        self.assertFalse(FileProcessJob.objects.exclude(status=FileProcessJobStatus.PENDING).filter(id__in=[job.id for job in jobs]).exists())

        callbacks[0]()
        self.assertEqual(mocked_delay.call_count, 2)

        for job in jobs:
            process_file_process_job(job.id)

        archive_file.refresh_from_db()
        refreshed_jobs = FileProcessJob.objects.filter(id__in=[job.id for job in jobs])
        self.assertFalse(refreshed_jobs.exclude(status=FileProcessJobStatus.SUCCESS).exists())
        self.assertEqual(archive_file.status, ArchiveFileStatus.ACTIVE)
        self.assertTrue(archive_file.thumbnail_path)
        self.assertIn("Scan Task PDF Text Extraction", archive_file.extracted_text or "")

        task_detail_response = self.client.get(f"/api/v1/digitization/scan-tasks/{task_id}/")
        self.assertEqual(task_detail_response.status_code, 200)
        self.assertEqual(task_detail_response.json()["data"]["status"], ScanTaskStatus.COMPLETED)
        self.assertEqual(task_detail_response.json()["data"]["completed_count"], 1)

    def test_upload_invalid_extension_should_fail(self) -> None:
        archive = self._create_archive("SCAN-2026-004")
        create_response = self.client.post(
            "/api/v1/digitization/scan-tasks/",
            {
                "task_name": "非法文件任务",
                "archive_ids": [archive.id],
            },
            format="json",
        )
        task_item_id = create_response.json()["data"]["items"][0]["id"]
        invalid_file = SimpleUploadedFile("invalid.exe", b"fake", content_type="application/octet-stream")

        response = self.client.post(
            f"/api/v1/digitization/scan-task-items/{task_item_id}/upload-files/",
            {"files": [invalid_file]},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)

    @override_settings(ARCHIVE_UPLOAD_MAX_SIZE_MB=1)
    def test_upload_oversized_file_should_fail(self) -> None:
        archive = self._create_archive("SCAN-2026-005")
        create_response = self.client.post(
            "/api/v1/digitization/scan-tasks/",
            {
                "task_name": "超大文件任务",
                "archive_ids": [archive.id],
            },
            format="json",
        )
        task_item_id = create_response.json()["data"]["items"][0]["id"]
        oversized_file = SimpleUploadedFile(
            "too-large.pdf",
            b"0" * (1024 * 1024 + 1),
            content_type="application/pdf",
        )

        response = self.client.post(
            f"/api/v1/digitization/scan-task-items/{task_item_id}/upload-files/",
            {"files": [oversized_file]},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "单个文件大小不能超过 1 MB。")
        self.assertFalse(ArchiveFile.objects.filter(scan_task_item_id=task_item_id).exists())

    def test_user_with_scan_permissions_should_create_scan_task(self) -> None:
        archive = self._create_archive("SCAN-2026-099")
        self.client.force_authenticate(self.scan_operator_user)

        response = self.client.post(
            "/api/v1/digitization/scan-tasks/",
            {
                "task_name": "权限化扫描任务",
                "archive_ids": [archive.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["task_name"], "权限化扫描任务")
