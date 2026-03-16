from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import DataScope, Role, SystemPermission
from apps.accounts.services import assign_permissions_to_role, assign_roles_to_user
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class ManagementApiTests(APITestCase):
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
        self.user_manage_permission = SystemPermission.objects.create(
            permission_code="button.system.user.manage",
            permission_name="维护用户",
            permission_type="BUTTON",
            module_name="system",
            sort_order=360,
            status=True,
        )
        self.role_manage_permission = SystemPermission.objects.create(
            permission_code="button.system.role.manage",
            permission_name="维护角色",
            permission_type="BUTTON",
            module_name="system",
            sort_order=370,
            status=True,
        )
        self.permission_manage_permission = SystemPermission.objects.create(
            permission_code="button.system.permission.manage",
            permission_name="维护权限项",
            permission_type="BUTTON",
            module_name="system",
            sort_order=380,
            status=True,
        )
        self.admin_user = User.objects.create_user(
            username="admin",
            password="Admin12345",
            real_name="系统管理员",
            dept=self.department,
            is_staff=True,
        )
        assign_roles_to_user(self.admin_user, [self.admin_role.id])

        self.user_manager_role = Role.objects.create(
            role_code="USER_MANAGER",
            role_name="用户管理员",
            data_scope=DataScope.ALL,
        )
        assign_permissions_to_role(self.user_manager_role, [self.user_manage_permission.id])
        self.user_manager_user = User.objects.create_user(
            username="user_manager",
            password="UserManager123",
            real_name="用户管理员",
            dept=self.department,
            is_staff=True,
        )
        assign_roles_to_user(self.user_manager_user, [self.user_manager_role.id])

        self.role_manager_role = Role.objects.create(
            role_code="ROLE_MANAGER",
            role_name="角色管理员",
            data_scope=DataScope.ALL,
        )
        assign_permissions_to_role(self.role_manager_role, [self.role_manage_permission.id])
        self.role_manager_user = User.objects.create_user(
            username="role_manager",
            password="RoleManager123",
            real_name="角色管理员",
            dept=self.department,
            is_staff=True,
        )
        assign_roles_to_user(self.role_manager_user, [self.role_manager_role.id])

        self.general_user = User.objects.create_user(
            username="general_user",
            password="General12345",
            real_name="普通用户",
            dept=self.department,
        )
        self.client.force_authenticate(self.admin_user)

    def test_admin_can_create_permission_role_and_user(self) -> None:
        permission_response = self.client.post(
            "/api/v1/accounts/permissions/",
            {
                "permission_code": "borrow_approve",
                "permission_name": "借阅审批",
                "permission_type": "API",
                "module_name": "borrowing",
                "route_path": "/api/v1/borrow-applications/{id}/approve/",
                "sort_order": 1,
                "status": True,
            },
            format="json",
        )
        self.assertEqual(permission_response.status_code, 201)

        role_response = self.client.post(
            "/api/v1/accounts/roles/",
            {
                "role_code": "ARCHIVIST",
                "role_name": "档案员",
                "data_scope": "DEPT",
                "status": True,
                "permission_ids": [permission_response.json()["data"]["id"]],
            },
            format="json",
        )
        self.assertEqual(role_response.status_code, 201)

        user_response = self.client.post(
            "/api/v1/accounts/users/",
            {
                "dept_id": self.department.id,
                "username": "archivist",
                "password": "Archivist123",
                "real_name": "档案员甲",
                "status": True,
                "role_ids": [role_response.json()["data"]["id"]],
                "security_clearance_level": "INTERNAL",
                "is_staff": True,
            },
            format="json",
        )

        self.assertEqual(user_response.status_code, 201)
        self.assertEqual(user_response.json()["data"]["username"], "archivist")
        self.assertEqual(len(user_response.json()["data"]["roles"]), 1)

    def test_permission_parent_should_not_allow_self_reference(self) -> None:
        permission_response = self.client.post(
            "/api/v1/accounts/permissions/",
            {
                "permission_code": "archive_search",
                "permission_name": "档案检索",
                "permission_type": "MENU",
                "module_name": "archives",
                "route_path": "/archives/records",
                "sort_order": 1,
                "status": True,
            },
            format="json",
        )
        self.assertEqual(permission_response.status_code, 201)

        permission_id = permission_response.json()["data"]["id"]
        update_response = self.client.put(
            f"/api/v1/accounts/permissions/{permission_id}/",
            {
                "parent_id": permission_id,
                "permission_code": "archive_search",
                "permission_name": "档案检索",
                "permission_type": "MENU",
                "module_name": "archives",
                "route_path": "/archives/records",
                "sort_order": 1,
                "status": True,
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, 400)
        self.assertEqual(update_response.json()["message"], "上级权限不能选择自己。")
        self.assertIsNone(SystemPermission.objects.get(id=permission_id).parent_id)

    def test_admin_can_get_permission_templates(self) -> None:
        response = self.client.get("/api/v1/accounts/permission-templates/")

        self.assertEqual(response.status_code, 200)
        templates = {item["role_code"]: item for item in response.json()["data"]}
        self.assertIn("ADMIN", templates)
        self.assertIn("ARCHIVIST", templates)
        self.assertIn("button.notification.reminder.dispatch", templates["ARCHIVIST"]["permission_codes"])
        self.assertIn("menu.borrow_center", templates["BORROWER"]["permission_codes"])
        self.assertNotIn("menu.archive_center", templates["BORROWER"]["permission_codes"])
        self.assertIn("menu.audit_log", templates["AUDITOR"]["permission_codes"])
        self.assertNotIn("menu.archive_center", templates["AUDITOR"]["permission_codes"])
        self.assertNotIn("menu.destruction_center", templates["AUDITOR"]["permission_codes"])

    def test_user_manager_can_list_users_roles_and_unlock_user(self) -> None:
        self.general_user.failed_login_count = 3
        self.general_user.lock_until_at = timezone.now()
        self.general_user.save(update_fields=["failed_login_count", "lock_until_at", "updated_at"])

        self.client.force_authenticate(self.user_manager_user)

        users_response = self.client.get("/api/v1/accounts/users/")
        roles_response = self.client.get("/api/v1/accounts/roles/")
        unlock_response = self.client.post(f"/api/v1/auth/unlock/{self.general_user.id}/")
        create_role_response = self.client.post(
            "/api/v1/accounts/roles/",
            {
                "role_code": "SHOULD_FAIL",
                "role_name": "不应创建成功",
                "data_scope": "SELF",
                "status": True,
                "permission_ids": [],
            },
            format="json",
        )

        self.assertEqual(users_response.status_code, 200)
        self.assertEqual(roles_response.status_code, 200)
        self.assertEqual(unlock_response.status_code, 200)
        self.assertEqual(create_role_response.status_code, 403)

        self.general_user.refresh_from_db()
        self.assertEqual(self.general_user.failed_login_count, 0)
        self.assertIsNone(self.general_user.lock_until_at)

    def test_role_manager_can_list_permission_catalog_and_templates_but_cannot_manage_users(self) -> None:
        self.client.force_authenticate(self.role_manager_user)

        permissions_response = self.client.get("/api/v1/accounts/permissions/")
        templates_response = self.client.get("/api/v1/accounts/permission-templates/")
        users_response = self.client.get("/api/v1/accounts/users/")
        create_permission_response = self.client.post(
            "/api/v1/accounts/permissions/",
            {
                "permission_code": "should_fail",
                "permission_name": "不应创建成功",
                "permission_type": "API",
                "module_name": "system",
                "route_path": "/api/v1/should-fail/",
                "sort_order": 999,
                "status": True,
            },
            format="json",
        )

        self.assertEqual(permissions_response.status_code, 200)
        self.assertEqual(templates_response.status_code, 200)
        self.assertEqual(users_response.status_code, 403)
        self.assertEqual(create_permission_response.status_code, 403)
