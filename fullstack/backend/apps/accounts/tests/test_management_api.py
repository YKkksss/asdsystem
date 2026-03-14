from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import DataScope, Role, SystemPermission
from apps.accounts.services import assign_roles_to_user
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
        self.admin_user = User.objects.create_user(
            username="admin",
            password="Admin12345",
            real_name="系统管理员",
            dept=self.department,
            is_staff=True,
        )
        assign_roles_to_user(self.admin_user, [self.admin_role.id])
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
