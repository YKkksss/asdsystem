from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import DataScope, Role, SystemPermission
from apps.accounts.services import assign_permissions_to_role, assign_roles_to_user
from apps.audit.models import AuditLog
from apps.audit.services import record_audit_log
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class AuditApiTests(APITestCase):
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
        )
        self.auditor_role = Role.objects.create(
            role_code="AUDITOR",
            role_name="审计员",
            data_scope=DataScope.ALL,
        )
        self.borrower_role = Role.objects.create(
            role_code="BORROWER",
            role_name="借阅人",
            data_scope=DataScope.SELF,
        )
        self.audit_menu_permission = SystemPermission.objects.create(
            permission_code="menu.audit_log",
            permission_name="审计日志",
            permission_type="MENU",
            module_name="audit",
            route_path="/audit/logs",
            sort_order=120,
            status=True,
        )
        self.audit_permission_role = Role.objects.create(
            role_code="AUDIT_VIEWER_PERMISSION",
            role_name="审计查看权限角色",
            data_scope=DataScope.ALL,
        )
        assign_permissions_to_role(self.audit_permission_role, [self.audit_menu_permission.id])

        self.admin_user = User.objects.create_user(
            username="audit_admin",
            password="Admin12345",
            real_name="管理员甲",
            dept=self.department,
            is_staff=True,
        )
        assign_roles_to_user(self.admin_user, [self.admin_role.id])

        self.auditor_user = User.objects.create_user(
            username="audit_user",
            password="Auditor12345",
            real_name="审计员甲",
            dept=self.department,
            is_staff=True,
        )
        assign_roles_to_user(self.auditor_user, [self.auditor_role.id])

        self.borrower_user = User.objects.create_user(
            username="reader_user",
            password="Reader12345",
            real_name="普通用户",
            dept=self.department,
        )
        assign_roles_to_user(self.borrower_user, [self.borrower_role.id])
        self.audit_permission_user = User.objects.create_user(
            username="audit_permission_user",
            password="AuditPermission12345",
            real_name="权限审计查看人",
            dept=self.department,
            is_staff=True,
        )
        assign_roles_to_user(self.audit_permission_user, [self.audit_permission_role.id])

        record_audit_log(
            module_name="ARCHIVES",
            action_code="ARCHIVE_CREATE",
            description="创建档案测试日志",
            user=self.admin_user,
            biz_type="archive_record",
            biz_id=1,
            target_repr="A2026-TEST",
        )
        record_audit_log(
            module_name="AUTH",
            action_code="LOGIN_FAILED",
            description="登录失败测试日志",
            user=self.borrower_user,
            biz_type="system_user",
            biz_id=self.borrower_user.id,
            target_repr=self.borrower_user.username,
            result_status="FAILED",
        )

    def test_auditor_should_view_audit_logs_and_summary(self) -> None:
        self.client.force_authenticate(self.auditor_user)

        list_response = self.client.get("/api/v1/audit/logs/", {"module_name": "ARCHIVES"})
        summary_response = self.client.get("/api/v1/audit/summary/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.json()["data"]), 1)
        self.assertEqual(list_response.json()["data"][0]["action_code"], "ARCHIVE_CREATE")

        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(summary_response.json()["data"]["total_count"], AuditLog.objects.count())
        self.assertEqual(summary_response.json()["data"]["failed_count"], 1)

    def test_non_audit_user_should_not_view_audit_logs(self) -> None:
        self.client.force_authenticate(self.borrower_user)
        response = self.client.get("/api/v1/audit/logs/")
        self.assertEqual(response.status_code, 403)

    def test_audit_log_list_should_support_optional_pagination(self) -> None:
        for index in range(3):
            record_audit_log(
                module_name="BORROWING",
                action_code=f"BORROW_LOG_{index + 1}",
                description=f"借阅日志{index + 1}",
                user=self.admin_user,
                biz_type="borrow_application",
                biz_id=index + 10,
                target_repr=f"B{index + 1}",
            )

        self.client.force_authenticate(self.auditor_user)
        response = self.client.get("/api/v1/audit/logs/", {"page": 2, "page_size": 2})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["pagination"]["page"], 2)
        self.assertEqual(response.json()["data"]["pagination"]["page_size"], 2)
        self.assertEqual(response.json()["data"]["pagination"]["total"], 5)
        self.assertEqual(response.json()["data"]["pagination"]["total_pages"], 3)
        self.assertEqual(len(response.json()["data"]["items"]), 2)

    def test_user_with_audit_menu_permission_should_view_audit_logs(self) -> None:
        self.client.force_authenticate(self.audit_permission_user)

        list_response = self.client.get("/api/v1/audit/logs/")
        summary_response = self.client.get("/api/v1/audit/summary/")

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(summary_response.status_code, 200)
