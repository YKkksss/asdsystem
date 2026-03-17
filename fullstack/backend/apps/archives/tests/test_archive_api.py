import shutil
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient, APITestCase

from apps.audit.models import AuditLog
from apps.accounts.models import DataScope, Role, SecurityClearance, SystemPermission
from apps.accounts.services import assign_permissions_to_role, assign_roles_to_user
from apps.archives.models import ArchiveCodeType, ArchiveFile, ArchiveRecord, ArchiveStatus, ArchiveStorageLocation
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class ArchiveApiTests(APITestCase):
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
        self.business_department = Department.objects.create(
            dept_code="BUS",
            dept_name="业务部",
            parent=self.department,
        )
        sync_department_hierarchy(self.business_department)
        self.business_child_department = Department.objects.create(
            dept_code="BUS_CHILD",
            dept_name="业务一部",
            parent=self.business_department,
        )
        sync_department_hierarchy(self.business_child_department)
        self.audit_department = Department.objects.create(
            dept_code="AUD",
            dept_name="审计部",
            parent=self.department,
        )
        sync_department_hierarchy(self.audit_department)

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
        self.dept_and_child_role = Role.objects.create(
            role_code="BUS_MANAGER",
            role_name="业务主管",
            data_scope=DataScope.DEPT_AND_CHILD,
            status=True,
        )
        self.archive_viewer_role = Role.objects.create(
            role_code="ARCHIVE_VIEWER_SELF",
            role_name="档案检索人员",
            data_scope=DataScope.SELF,
            status=True,
        )
        self.archive_center_permission = SystemPermission.objects.create(
            permission_code="menu.archive_center",
            permission_name="档案中心",
            permission_type="MENU",
            module_name="archives",
            route_path="/archives/records",
            sort_order=20,
            status=True,
        )
        assign_permissions_to_role(self.dept_and_child_role, [self.archive_center_permission.id])
        assign_permissions_to_role(self.archive_viewer_role, [self.archive_center_permission.id])
        self.user = User.objects.create_user(
            username="archivist",
            password="Archivist123",
            real_name="档案员甲",
            dept=self.department,
            is_staff=True,
            security_clearance_level=SecurityClearance.TOP_SECRET,
        )
        assign_roles_to_user(self.user, [self.archivist_role.id])
        self.low_clearance_user = User.objects.create_user(
            username="reader",
            password="Reader12345",
            real_name="查阅人员",
            dept=self.department,
            security_clearance_level=SecurityClearance.INTERNAL,
        )
        assign_roles_to_user(self.low_clearance_user, [self.borrower_role.id, self.archive_viewer_role.id])
        self.business_scope_user = User.objects.create_user(
            username="business_reader",
            password="BusinessReader12345",
            real_name="业务查阅人",
            dept=self.business_department,
            security_clearance_level=SecurityClearance.TOP_SECRET,
        )
        assign_roles_to_user(self.business_scope_user, [self.borrower_role.id, self.archive_viewer_role.id])
        self.business_manager_user = User.objects.create_user(
            username="business_manager",
            password="BusinessManager12345",
            real_name="业务主管",
            dept=self.business_department,
            security_clearance_level=SecurityClearance.TOP_SECRET,
        )
        assign_roles_to_user(self.business_manager_user, [self.dept_and_child_role.id])
        self.client.force_authenticate(self.user)

    def tearDown(self) -> None:
        self.media_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)
        super().tearDown()

    def _create_location(self) -> int:
        response = self.client.post(
            "/api/v1/archives/storage-locations/",
            {
                "warehouse_name": "一号库房",
                "area_name": "A区",
                "cabinet_code": "G01",
                "rack_code": "J01",
                "layer_code": "L01",
                "box_code": "H01",
                "status": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["full_location_code"], "一号库房/A区/G01/J01/L01/H01")
        return response.json()["data"]["id"]

    def _create_archive_record(
        self,
        *,
        archive_code: str,
        title: str,
        responsible_dept: Department | None = None,
        location_id: int | None = None,
        security_level: str = SecurityClearance.INTERNAL,
        status: str = ArchiveStatus.ON_SHELF,
        created_by: int | None = None,
        responsible_person: str = "责任人甲",
    ) -> ArchiveRecord:
        operator_id = created_by or self.user.id
        return ArchiveRecord.objects.create(
            archive_code=archive_code,
            title=title,
            year=2026,
            retention_period="长期",
            security_level=security_level,
            status=status,
            responsible_dept=responsible_dept,
            responsible_person=responsible_person,
            location_id=location_id,
            created_by=operator_id,
            updated_by=operator_id,
        )

    def test_create_archive_should_create_initial_revision(self) -> None:
        location_id = self._create_location()

        response = self.client.post(
            "/api/v1/archives/records/",
            {
                "archive_code": "A2026-0001",
                "title": "综合档案目录",
                "year": 2026,
                "retention_period": "长期",
                "security_level": SecurityClearance.INTERNAL,
                "responsible_dept_id": self.department.id,
                "responsible_person": "张三",
                "formed_at": "2026-03-01",
                "keywords": "档案,目录",
                "summary": "用于测试档案创建流程",
                "page_count": 12,
                "carrier_type": "纸质",
                "location_id": location_id,
                "revision_remark": "首次入库",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["status"], ArchiveStatus.DRAFT)
        self.assertEqual(len(response.json()["data"]["revisions"]), 1)
        self.assertEqual(response.json()["data"]["revisions"][0]["remark"], "首次入库")

    def test_create_archive_should_reject_responsible_department_out_of_data_scope(self) -> None:
        location_id = self._create_location()

        response = self.client.post(
            "/api/v1/archives/records/",
            {
                "archive_code": "A2026-0010",
                "title": "跨范围建档测试",
                "year": 2026,
                "retention_period": "长期",
                "security_level": SecurityClearance.INTERNAL,
                "responsible_dept_id": self.business_department.id,
                "responsible_person": "张三",
                "formed_at": "2026-03-01",
                "keywords": "档案,权限",
                "summary": "用于测试跨范围建档拦截",
                "page_count": 12,
                "carrier_type": "纸质",
                "location_id": location_id,
                "revision_remark": "首次入库",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("所属范围外", response.json()["message"])
        self.assertFalse(ArchiveRecord.objects.filter(archive_code="A2026-0010").exists())

    def test_update_archive_should_reject_move_to_out_of_scope_department(self) -> None:
        location_id = self._create_location()
        archive = self._create_archive_record(
            archive_code="A2026-0011",
            title="档案范围更新测试",
            responsible_dept=self.department,
            location_id=location_id,
        )

        response = self.client.put(
            f"/api/v1/archives/records/{archive.id}/",
            {
                "archive_code": archive.archive_code,
                "title": archive.title,
                "year": archive.year,
                "retention_period": archive.retention_period,
                "security_level": archive.security_level,
                "responsible_dept_id": self.business_department.id,
                "responsible_person": archive.responsible_person,
                "formed_at": "2026-03-01",
                "keywords": "档案,更新",
                "summary": "用于测试跨范围更新拦截",
                "page_count": 8,
                "carrier_type": "纸质",
                "location_id": location_id,
                "revision_remark": "尝试调整责任部门",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("所属范围外", response.json()["message"])
        archive.refresh_from_db()
        self.assertEqual(archive.responsible_dept_id, self.department.id)

    def test_update_archive_should_create_revision_and_write_audit_log(self) -> None:
        location_id = self._create_location()
        next_location_response = self.client.post(
            "/api/v1/archives/storage-locations/",
            {
                "warehouse_name": "二号库房",
                "area_name": "B区",
                "cabinet_code": "G09",
                "rack_code": "J02",
                "layer_code": "L03",
                "box_code": "H08",
                "status": True,
            },
            format="json",
        )
        self.assertEqual(next_location_response.status_code, 201)
        next_location_id = next_location_response.json()["data"]["id"]

        archive_response = self.client.post(
            "/api/v1/archives/records/",
            {
                "archive_code": "A2026-0009",
                "title": "综合档案目录",
                "year": 2026,
                "retention_period": "长期",
                "security_level": SecurityClearance.INTERNAL,
                "responsible_dept_id": self.department.id,
                "responsible_person": "张三",
                "formed_at": "2026-03-01",
                "keywords": "档案,目录",
                "summary": "用于测试档案更新流程",
                "page_count": 12,
                "carrier_type": "纸质",
                "location_id": location_id,
                "revision_remark": "首次入库",
            },
            format="json",
        )
        self.assertEqual(archive_response.status_code, 201)
        archive_id = archive_response.json()["data"]["id"]

        response = self.client.put(
            f"/api/v1/archives/records/{archive_id}/",
            {
                "archive_code": "A2026-0009",
                "title": "综合档案目录（修订版）",
                "year": 2026,
                "retention_period": "长期",
                "security_level": SecurityClearance.INTERNAL,
                "responsible_dept_id": self.department.id,
                "responsible_person": "李四",
                "formed_at": "2026-03-01",
                "keywords": "档案,目录,修订",
                "summary": "补充了责任信息与库位调整说明",
                "page_count": 18,
                "carrier_type": "纸质",
                "location_id": next_location_id,
                "revision_remark": "补充摘要与调整库位",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["title"], "综合档案目录（修订版）")
        self.assertEqual(response.json()["data"]["location_id"], next_location_id)
        self.assertEqual(len(response.json()["data"]["revisions"]), 2)
        self.assertEqual(response.json()["data"]["revisions"][0]["revision_no"], 2)
        self.assertEqual(response.json()["data"]["revisions"][0]["remark"], "补充摘要与调整库位")
        self.assertIn("title", response.json()["data"]["revisions"][0]["changed_fields_json"])
        self.assertIn("location_id", response.json()["data"]["revisions"][0]["changed_fields_json"])
        self.assertTrue(AuditLog.objects.filter(action_code="ARCHIVE_UPDATE", biz_id=archive_id).exists())

    def test_update_storage_location_should_refresh_full_location_code(self) -> None:
        location_id = self._create_location()

        response = self.client.put(
            f"/api/v1/archives/storage-locations/{location_id}/",
            {
                "warehouse_name": "二号库房",
                "area_name": "B区",
                "cabinet_code": "G09",
                "rack_code": "J02",
                "layer_code": "L03",
                "box_code": "H08",
                "status": False,
                "remark": "库位调整后停用",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["full_location_code"], "二号库房/B区/G09/J02/L03/H08")
        self.assertEqual(response.json()["data"]["updated_by"], self.user.id)
        location = ArchiveStorageLocation.objects.get(id=location_id)
        self.assertEqual(location.full_location_code, "二号库房/B区/G09/J02/L03/H08")
        self.assertFalse(location.status)

    def test_generate_codes_should_create_barcode_and_qrcode_files(self) -> None:
        location_id = self._create_location()
        archive_response = self.client.post(
            "/api/v1/archives/records/",
            {
                "archive_code": "A2026-0002",
                "title": "年度归档清单",
                "year": 2026,
                "retention_period": "30年",
                "security_level": SecurityClearance.INTERNAL,
                "location_id": location_id,
            },
            format="json",
        )
        archive_id = archive_response.json()["data"]["id"]

        response = self.client.post(f"/api/v1/archives/records/{archive_id}/generate-codes/", format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]["barcodes"]), 2)
        code_types = {item["code_type"] for item in response.json()["data"]["barcodes"]}
        self.assertEqual(code_types, {ArchiveCodeType.BARCODE, ArchiveCodeType.QRCODE})
        for item in response.json()["data"]["barcodes"]:
            self.assertTrue(Path(self.media_root, item["image_path"]).exists())

    def test_print_codes_should_update_print_trace_and_write_audit_log(self) -> None:
        archive_response = self.client.post(
            "/api/v1/archives/records/",
            {
                "archive_code": "A2026-0010",
                "title": "标签打印档案",
                "year": 2026,
                "retention_period": "长期",
                "security_level": SecurityClearance.INTERNAL,
            },
            format="json",
        )
        archive_id = archive_response.json()["data"]["id"]

        generate_response = self.client.post(f"/api/v1/archives/records/{archive_id}/generate-codes/", format="json")
        self.assertEqual(generate_response.status_code, 200)

        response = self.client.post(f"/api/v1/archives/records/{archive_id}/print-codes/", format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "档案条码打印留痕成功")
        self.assertEqual(len(response.json()["data"]["barcodes"]), 2)
        for item in response.json()["data"]["barcodes"]:
            self.assertEqual(item["print_count"], 1)
            self.assertIsNotNone(item["last_printed_at"])
        self.assertTrue(AuditLog.objects.filter(action_code="ARCHIVE_CODE_PRINT", biz_id=archive_id).exists())

    def test_print_codes_should_reject_when_codes_not_generated(self) -> None:
        archive_response = self.client.post(
            "/api/v1/archives/records/",
            {
                "archive_code": "A2026-0011",
                "title": "未生成条码档案",
                "year": 2026,
                "retention_period": "长期",
                "security_level": SecurityClearance.INTERNAL,
            },
            format="json",
        )
        archive_id = archive_response.json()["data"]["id"]

        response = self.client.post(f"/api/v1/archives/records/{archive_id}/print-codes/", format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["message"], "请先生成档案条码或二维码后再执行打印。")
        self.assertFalse(AuditLog.objects.filter(action_code="ARCHIVE_CODE_PRINT", biz_id=archive_id).exists())

    def test_batch_print_codes_should_update_all_archives_and_keep_request_order(self) -> None:
        first_archive_response = self.client.post(
            "/api/v1/archives/records/",
            {
                "archive_code": "A2026-0012",
                "title": "第一份打印档案",
                "year": 2026,
                "retention_period": "长期",
                "security_level": SecurityClearance.INTERNAL,
            },
            format="json",
        )
        second_archive_response = self.client.post(
            "/api/v1/archives/records/",
            {
                "archive_code": "A2026-0013",
                "title": "第二份打印档案",
                "year": 2026,
                "retention_period": "长期",
                "security_level": SecurityClearance.INTERNAL,
            },
            format="json",
        )
        first_archive_id = first_archive_response.json()["data"]["id"]
        second_archive_id = second_archive_response.json()["data"]["id"]

        self.client.post(f"/api/v1/archives/records/{first_archive_id}/generate-codes/", format="json")
        self.client.post(f"/api/v1/archives/records/{second_archive_id}/generate-codes/", format="json")

        response = self.client.post(
            "/api/v1/archives/records/batch-print-codes/",
            {
                "archive_ids": [second_archive_id, first_archive_id, second_archive_id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["message"], "档案批量打印留痕成功")
        self.assertEqual(
            [item["id"] for item in response.json()["data"]],
            [second_archive_id, first_archive_id],
        )
        for archive_item in response.json()["data"]:
            for barcode_item in archive_item["barcodes"]:
                self.assertEqual(barcode_item["print_count"], 1)
                self.assertIsNotNone(barcode_item["last_printed_at"])
        self.assertTrue(AuditLog.objects.filter(action_code="ARCHIVE_CODE_PRINT", biz_id=first_archive_id).exists())
        self.assertTrue(AuditLog.objects.filter(action_code="ARCHIVE_CODE_PRINT", biz_id=second_archive_id).exists())

    def test_batch_print_codes_should_fail_atomically_when_any_archive_missing_codes(self) -> None:
        ready_archive_response = self.client.post(
            "/api/v1/archives/records/",
            {
                "archive_code": "A2026-0014",
                "title": "已生成码档案",
                "year": 2026,
                "retention_period": "长期",
                "security_level": SecurityClearance.INTERNAL,
            },
            format="json",
        )
        pending_archive_response = self.client.post(
            "/api/v1/archives/records/",
            {
                "archive_code": "A2026-0015",
                "title": "未生成码档案",
                "year": 2026,
                "retention_period": "长期",
                "security_level": SecurityClearance.INTERNAL,
            },
            format="json",
        )
        ready_archive_id = ready_archive_response.json()["data"]["id"]
        pending_archive_id = pending_archive_response.json()["data"]["id"]

        self.client.post(f"/api/v1/archives/records/{ready_archive_id}/generate-codes/", format="json")

        response = self.client.post(
            "/api/v1/archives/records/batch-print-codes/",
            {
                "archive_ids": [ready_archive_id, pending_archive_id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["message"],
            "以下档案尚未生成条码或二维码：A2026-0015。",
        )
        ready_archive = ArchiveRecord.objects.get(id=ready_archive_id)
        self.assertEqual(ready_archive.barcodes.first().print_count, 0)
        self.assertFalse(AuditLog.objects.filter(action_code="ARCHIVE_CODE_PRINT", biz_id=ready_archive_id).exists())
        self.assertFalse(AuditLog.objects.filter(action_code="ARCHIVE_CODE_PRINT", biz_id=pending_archive_id).exists())

    def test_transition_status_should_update_catalog_and_shelf_time(self) -> None:
        archive_response = self.client.post(
            "/api/v1/archives/records/",
            {
                "archive_code": "A2026-0003",
                "title": "馆藏目录",
                "year": 2026,
                "retention_period": "永久",
                "security_level": SecurityClearance.SECRET,
            },
            format="json",
        )
        archive_id = archive_response.json()["data"]["id"]

        pending_scan_response = self.client.post(
            f"/api/v1/archives/records/{archive_id}/transition-status/",
            {
                "next_status": ArchiveStatus.PENDING_SCAN,
                "remark": "提交扫描",
            },
            format="json",
        )
        self.assertEqual(pending_scan_response.status_code, 200)

        pending_catalog_response = self.client.post(
            f"/api/v1/archives/records/{archive_id}/transition-status/",
            {
                "next_status": ArchiveStatus.PENDING_CATALOG,
                "remark": "扫描完成",
            },
            format="json",
        )
        self.assertEqual(pending_catalog_response.status_code, 200)

        on_shelf_response = self.client.post(
            f"/api/v1/archives/records/{archive_id}/transition-status/",
            {
                "next_status": ArchiveStatus.ON_SHELF,
                "remark": "编目通过并上架",
            },
            format="json",
        )

        self.assertEqual(on_shelf_response.status_code, 200)
        self.assertEqual(on_shelf_response.json()["data"]["status"], ArchiveStatus.ON_SHELF)
        self.assertIsNotNone(on_shelf_response.json()["data"]["catalog_completed_at"])
        self.assertIsNotNone(on_shelf_response.json()["data"]["shelved_at"])
        self.assertEqual(len(on_shelf_response.json()["data"]["revisions"]), 4)

    def test_transition_to_borrowed_without_borrow_id_should_fail(self) -> None:
        archive_response = self.client.post(
            "/api/v1/archives/records/",
            {
                "archive_code": "A2026-0004",
                "title": "借阅测试档案",
                "year": 2026,
                "retention_period": "10年",
                "security_level": SecurityClearance.INTERNAL,
            },
            format="json",
        )
        archive_id = archive_response.json()["data"]["id"]

        self.client.post(
            f"/api/v1/archives/records/{archive_id}/transition-status/",
            {
                "next_status": ArchiveStatus.PENDING_SCAN,
            },
            format="json",
        )
        self.client.post(
            f"/api/v1/archives/records/{archive_id}/transition-status/",
            {
                "next_status": ArchiveStatus.PENDING_CATALOG,
            },
            format="json",
        )
        self.client.post(
            f"/api/v1/archives/records/{archive_id}/transition-status/",
            {
                "next_status": ArchiveStatus.ON_SHELF,
            },
            format="json",
        )

        response = self.client.post(
            f"/api/v1/archives/records/{archive_id}/transition-status/",
            {
                "next_status": ArchiveStatus.BORROWED,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_archive_list_should_support_keyword_filters_on_extracted_text(self) -> None:
        archive = ArchiveRecord.objects.create(
            archive_code="A2026-0005",
            title="全文检索样例档案",
            year=2026,
            retention_period="长期",
            security_level=SecurityClearance.INTERNAL,
            status=ArchiveStatus.PENDING_CATALOG,
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        ArchiveFile.objects.create(
            archive=archive,
            file_name="search-sample.pdf",
            file_path="archive-files/test/search-sample.pdf",
            file_ext="pdf",
            mime_type="application/pdf",
            file_size=1024,
            extracted_text="Alpha Search Text For Archive Retrieval",
            uploaded_by=self.user.id,
        )

        response = self.client.get(
            "/api/v1/archives/records/",
            {
                "keyword": "Alpha Search Text",
                "year": 2026,
                "security_level": SecurityClearance.INTERNAL,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]), 1)
        self.assertEqual(response.json()["data"][0]["archive_code"], "A2026-0005")

    def test_low_clearance_user_should_receive_masked_sensitive_fields(self) -> None:
        location_id = self._create_location()
        archive = ArchiveRecord.objects.create(
            archive_code="A2026-0006",
            title="高密级档案",
            year=2026,
            retention_period="永久",
            security_level=SecurityClearance.SECRET,
            status=ArchiveStatus.ON_SHELF,
            responsible_dept_id=self.department.id,
            responsible_person="李四",
            summary="这是需要脱敏的档案摘要。",
            location_id=location_id,
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        ArchiveFile.objects.create(
            archive=archive,
            file_name="secret.pdf",
            file_path="archive-files/test/secret.pdf",
            file_ext="pdf",
            mime_type="application/pdf",
            file_size=2048,
            extracted_text="Secret Archive Text",
            uploaded_by=self.user.id,
        )

        self.client.force_authenticate(self.low_clearance_user)
        response = self.client.get(f"/api/v1/archives/records/{archive.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["data"]["is_sensitive_masked"])
        self.assertIn("summary", response.json()["data"]["masked_fields"])
        self.assertEqual(response.json()["data"]["responsible_person"], "权限不足，责任者已脱敏。")
        self.assertEqual(response.json()["data"]["summary"], "权限不足，摘要已脱敏。")
        self.assertEqual(
            response.json()["data"]["location_detail"]["full_location_code"],
            "权限不足，隐藏实体精确位置。",
        )
        self.assertEqual(response.json()["data"]["files"][0]["status"], "MASKED")

    def test_archive_file_preview_and_download_should_issue_ticket_and_write_audit_log(self) -> None:
        archive = ArchiveRecord.objects.create(
            archive_code="A2026-0007",
            title="文件预览测试档案",
            year=2026,
            retention_period="长期",
            security_level=SecurityClearance.INTERNAL,
            status=ArchiveStatus.ON_SHELF,
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        relative_path = "archive-files/test/preview-sample.pdf"
        absolute_path = Path(self.media_root, relative_path)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(b"%PDF-1.4 preview sample")

        archive_file = ArchiveFile.objects.create(
            archive=archive,
            file_name="preview-sample.pdf",
            file_path=relative_path,
            file_ext="pdf",
            mime_type="application/pdf",
            file_size=absolute_path.stat().st_size,
            uploaded_by=self.user.id,
        )

        preview_ticket_response = self.client.post(
            f"/api/v1/archives/files/{archive_file.id}/preview-ticket/",
            format="json",
        )
        self.assertEqual(preview_ticket_response.status_code, 200)
        self.assertIn("watermark_text", preview_ticket_response.json()["data"])

        preview_content_response = self.client.get(preview_ticket_response.json()["data"]["access_url"])
        self.assertEqual(preview_content_response.status_code, 200)
        self.assertIn("inline", preview_content_response.get("Content-Disposition", "inline"))

        download_ticket_response = self.client.post(
            f"/api/v1/archives/files/{archive_file.id}/download-ticket/",
            {"purpose": "工作核验"},
            format="json",
        )
        self.assertEqual(download_ticket_response.status_code, 200)

        download_content_response = self.client.get(download_ticket_response.json()["data"]["access_url"])
        self.assertEqual(download_content_response.status_code, 200)
        self.assertIn("attachment", download_content_response["Content-Disposition"])

        self.assertTrue(AuditLog.objects.filter(action_code="ARCHIVE_FILE_PREVIEW_APPLY", biz_id=archive_file.id).exists())
        self.assertTrue(AuditLog.objects.filter(action_code="ARCHIVE_FILE_PREVIEW_ACCESS", biz_id=archive_file.id).exists())
        self.assertTrue(AuditLog.objects.filter(action_code="ARCHIVE_FILE_DOWNLOAD_APPLY", biz_id=archive_file.id).exists())
        self.assertTrue(AuditLog.objects.filter(action_code="ARCHIVE_FILE_DOWNLOAD_ACCESS", biz_id=archive_file.id).exists())

    def test_low_clearance_user_should_not_create_preview_ticket(self) -> None:
        archive = ArchiveRecord.objects.create(
            archive_code="A2026-0008",
            title="预览权限受限档案",
            year=2026,
            retention_period="长期",
            security_level=SecurityClearance.SECRET,
            status=ArchiveStatus.ON_SHELF,
            responsible_dept_id=self.department.id,
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        relative_path = "archive-files/test/secret-preview.pdf"
        absolute_path = Path(self.media_root, relative_path)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(b"%PDF-1.4 secret preview sample")

        archive_file = ArchiveFile.objects.create(
            archive=archive,
            file_name="secret-preview.pdf",
            file_path=relative_path,
            file_ext="pdf",
            mime_type="application/pdf",
            file_size=absolute_path.stat().st_size,
            uploaded_by=self.user.id,
        )

        self.client.force_authenticate(self.low_clearance_user)
        response = self.client.post(f"/api/v1/archives/files/{archive_file.id}/preview-ticket/", format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("当前账号无权访问该档案文件", response.json()["message"])

    def test_archive_list_should_apply_data_scope_for_self_role_user(self) -> None:
        location_id = self._create_location()
        self._create_archive_record(
            archive_code="A2026-1001",
            title="总部档案",
            responsible_dept=self.department,
            location_id=location_id,
        )
        self._create_archive_record(
            archive_code="A2026-1002",
            title="业务部档案",
            responsible_dept=self.business_department,
            location_id=location_id,
        )

        self.client.force_authenticate(self.business_scope_user)
        response = self.client.get("/api/v1/archives/records/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["archive_code"] for item in response.json()["data"]], ["A2026-1002"])

    def test_archive_detail_should_return_404_when_archive_is_out_of_data_scope(self) -> None:
        archive = self._create_archive_record(
            archive_code="A2026-1003",
            title="总部详情档案",
            responsible_dept=self.department,
        )

        self.client.force_authenticate(self.business_scope_user)
        response = self.client.get(f"/api/v1/archives/records/{archive.id}/")

        self.assertEqual(response.status_code, 404)

    def test_archive_file_tickets_should_reject_when_archive_is_out_of_data_scope(self) -> None:
        archive = self._create_archive_record(
            archive_code="A2026-1004",
            title="总部预览档案",
            responsible_dept=self.department,
        )
        relative_path = "archive-files/test/scope-preview.pdf"
        absolute_path = Path(self.media_root, relative_path)
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(b"%PDF-1.4 scope preview sample")

        archive_file = ArchiveFile.objects.create(
            archive=archive,
            file_name="scope-preview.pdf",
            file_path=relative_path,
            file_ext="pdf",
            mime_type="application/pdf",
            file_size=absolute_path.stat().st_size,
            uploaded_by=self.user.id,
        )

        self.client.force_authenticate(self.business_scope_user)
        preview_response = self.client.post(f"/api/v1/archives/files/{archive_file.id}/preview-ticket/", format="json")
        download_response = self.client.post(
            f"/api/v1/archives/files/{archive_file.id}/download-ticket/",
            {"purpose": "越权测试"},
            format="json",
        )

        self.assertEqual(preview_response.status_code, 403)
        self.assertIn("所属范围外的档案", preview_response.json()["message"])
        self.assertEqual(download_response.status_code, 403)
        self.assertIn("所属范围外的档案", download_response.json()["message"])

    def test_archive_list_should_include_child_departments_for_dept_and_child_scope(self) -> None:
        self._create_archive_record(
            archive_code="A2026-1005",
            title="业务部直属档案",
            responsible_dept=self.business_department,
        )
        self._create_archive_record(
            archive_code="A2026-1006",
            title="业务一部档案",
            responsible_dept=self.business_child_department,
        )
        self._create_archive_record(
            archive_code="A2026-1007",
            title="审计部档案",
            responsible_dept=self.audit_department,
        )

        self.client.force_authenticate(self.business_manager_user)
        response = self.client.get("/api/v1/archives/records/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["archive_code"] for item in response.json()["data"]],
            ["A2026-1005", "A2026-1006"],
        )

    def test_archive_list_should_support_optional_pagination(self) -> None:
        for index in range(5):
            self._create_archive_record(
                archive_code=f"A2026-P{index + 1:03d}",
                title=f"分页档案{index + 1}",
                responsible_dept=self.department,
            )

        response = self.client.get(
            "/api/v1/archives/records/",
            {"page": 2, "page_size": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["pagination"]["page"], 2)
        self.assertEqual(response.json()["data"]["pagination"]["page_size"], 2)
        self.assertEqual(response.json()["data"]["pagination"]["total"], 5)
        self.assertEqual(response.json()["data"]["pagination"]["total_pages"], 3)
        self.assertEqual(len(response.json()["data"]["items"]), 2)
        self.assertEqual(
            [item["archive_code"] for item in response.json()["data"]["items"]],
            ["A2026-P003", "A2026-P004"],
        )
