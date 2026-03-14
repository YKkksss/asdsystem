from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import DataScope, Role, SecurityClearance
from apps.accounts.services import assign_roles_to_user
from apps.archives.models import ArchiveRecord, ArchiveStatus
from apps.audit.models import AuditLog
from apps.borrowing.models import BorrowApplication, BorrowApplicationStatus
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class ReportsApiTests(APITestCase):
    def setUp(self) -> None:
        self.client = APIClient()

        self.root_department = Department.objects.create(
            dept_code="ROOT",
            dept_name="总部",
        )
        sync_department_hierarchy(self.root_department)

        self.archive_department = Department.objects.create(
            dept_code="ARC",
            dept_name="档案室",
            parent=self.root_department,
        )
        sync_department_hierarchy(self.archive_department)

        self.business_department = Department.objects.create(
            dept_code="BUS",
            dept_name="业务部",
            parent=self.root_department,
        )
        sync_department_hierarchy(self.business_department)

        self.admin_role = Role.objects.create(role_code="ADMIN", role_name="管理员", data_scope=DataScope.ALL, status=True)
        self.archivist_role = Role.objects.create(
            role_code="ARCHIVIST",
            role_name="档案员",
            data_scope=DataScope.DEPT,
            status=True,
        )
        self.auditor_role = Role.objects.create(
            role_code="AUDITOR",
            role_name="审计员",
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
            username="report_admin",
            password="Admin12345",
            real_name="管理员甲",
            dept=self.root_department,
            is_staff=True,
        )
        assign_roles_to_user(self.admin_user, [self.admin_role.id])

        self.auditor_user = User.objects.create_user(
            username="report_auditor",
            password="Auditor12345",
            real_name="审计员甲",
            dept=self.root_department,
            is_staff=True,
        )
        assign_roles_to_user(self.auditor_user, [self.auditor_role.id])

        self.archivist_user = User.objects.create_user(
            username="report_archivist",
            password="Archivist12345",
            real_name="档案员甲",
            dept=self.archive_department,
            is_staff=True,
        )
        assign_roles_to_user(self.archivist_user, [self.archivist_role.id])

        self.borrower_user = User.objects.create_user(
            username="report_borrower",
            password="Borrower12345",
            real_name="借阅人甲",
            dept=self.business_department,
        )
        assign_roles_to_user(self.borrower_user, [self.borrower_role.id])

        self.archive_a = ArchiveRecord.objects.create(
            archive_code="A2026-R001",
            title="合同档案",
            year=2026,
            retention_period="长期",
            security_level=SecurityClearance.INTERNAL,
            status=ArchiveStatus.ON_SHELF,
            carrier_type="纸质",
            responsible_dept=self.archive_department,
            created_by=self.archivist_user.id,
            updated_by=self.archivist_user.id,
        )
        self.archive_b = ArchiveRecord.objects.create(
            archive_code="A2026-R002",
            title="项目档案",
            year=2026,
            retention_period="长期",
            security_level=SecurityClearance.SECRET,
            status=ArchiveStatus.BORROWED,
            carrier_type="电子",
            responsible_dept=self.archive_department,
            created_by=self.archivist_user.id,
            updated_by=self.archivist_user.id,
        )

        BorrowApplication.objects.create(
            application_no="BOR-R001",
            archive=self.archive_a,
            applicant=self.borrower_user,
            applicant_dept=self.business_department,
            purpose="工作查阅",
            expected_return_at="2026-03-20T09:00:00+08:00",
            status=BorrowApplicationStatus.RETURNED,
            returned_at="2026-03-18T09:00:00+08:00",
            is_overdue=False,
            overdue_days=0,
            created_by=self.borrower_user.id,
            updated_by=self.archivist_user.id,
        )
        BorrowApplication.objects.create(
            application_no="BOR-R002",
            archive=self.archive_a,
            applicant=self.borrower_user,
            applicant_dept=self.business_department,
            purpose="利用查阅",
            expected_return_at="2026-03-10T09:00:00+08:00",
            status=BorrowApplicationStatus.OVERDUE,
            is_overdue=True,
            overdue_days=3,
            created_by=self.borrower_user.id,
            updated_by=self.archivist_user.id,
        )
        BorrowApplication.objects.create(
            application_no="BOR-R003",
            archive=self.archive_b,
            applicant=self.archivist_user,
            applicant_dept=self.archive_department,
            purpose="编研使用",
            expected_return_at="2026-03-22T09:00:00+08:00",
            status=BorrowApplicationStatus.CHECKED_OUT,
            is_overdue=False,
            overdue_days=0,
            created_by=self.archivist_user.id,
            updated_by=self.archivist_user.id,
        )

    def test_report_summary_and_lists_should_return_expected_statistics(self) -> None:
        self.client.force_authenticate(self.auditor_user)

        summary_response = self.client.get("/api/v1/reports/summary/")
        department_response = self.client.get("/api/v1/reports/departments/")
        archive_response = self.client.get("/api/v1/reports/archives/")

        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(summary_response.json()["data"]["total_borrow_count"], 3)
        self.assertEqual(summary_response.json()["data"]["overdue_count"], 1)
        self.assertEqual(summary_response.json()["data"]["returned_count"], 1)
        self.assertEqual(summary_response.json()["data"]["utilized_archive_count"], 2)

        self.assertEqual(department_response.status_code, 200)
        self.assertEqual(len(department_response.json()["data"]), 2)
        self.assertEqual(department_response.json()["data"][0]["applicant_dept_name"], "业务部")
        self.assertEqual(department_response.json()["data"][0]["borrow_count"], 2)

        self.assertEqual(archive_response.status_code, 200)
        self.assertEqual(len(archive_response.json()["data"]), 2)
        self.assertEqual(archive_response.json()["data"][0]["archive_code"], "A2026-R001")
        self.assertEqual(archive_response.json()["data"][0]["borrow_count"], 2)

    def test_report_export_should_return_csv_and_write_audit_log(self) -> None:
        self.client.force_authenticate(self.admin_user)

        response = self.client.get(
            "/api/v1/reports/export/",
            {"report_type": "departments", "archive_security_level": SecurityClearance.INTERNAL},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])
        content = response.content.decode("utf-8")
        self.assertIn("applicant_dept_name", content)
        self.assertIn("业务部", content)
        self.assertTrue(
            AuditLog.objects.filter(module_name="REPORTS", action_code="REPORT_EXPORT", username="report_admin").exists()
        )

    def test_borrower_should_not_view_reports(self) -> None:
        self.client.force_authenticate(self.borrower_user)
        response = self.client.get("/api/v1/reports/summary/")
        self.assertEqual(response.status_code, 403)
