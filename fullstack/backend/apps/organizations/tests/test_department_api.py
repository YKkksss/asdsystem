from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from apps.accounts.models import DataScope, Role
from apps.accounts.services import assign_roles_to_user
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class DepartmentApiTests(APITestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.root_department = Department.objects.create(
            dept_code="ROOT",
            dept_name="总部",
        )
        sync_department_hierarchy(self.root_department)

        self.admin_role = Role.objects.create(
            role_code="ADMIN",
            role_name="管理员",
            data_scope=DataScope.ALL,
        )
        self.admin_user = User.objects.create_user(
            username="admin",
            password="Admin12345",
            real_name="系统管理员",
            dept=self.root_department,
            is_staff=True,
        )
        assign_roles_to_user(self.admin_user, [self.admin_role.id])
        self.client.force_authenticate(self.admin_user)

    def test_create_department_should_build_tree_path(self) -> None:
        response = self.client.post(
            "/api/v1/organizations/departments/",
            {
                "parent_id": self.root_department.id,
                "dept_code": "ARCHIVE",
                "dept_name": "档案室",
                "sort_order": 10,
                "status": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["data"]["dept_level"], 2)
        self.assertTrue(
            response.json()["data"]["dept_path"].startswith(self.root_department.dept_path)
        )

    def test_department_tree_should_return_nested_nodes(self) -> None:
        child = Department.objects.create(
            parent=self.root_department,
            dept_code="CHILD",
            dept_name="子部门",
        )
        sync_department_hierarchy(child)

        response = self.client.get("/api/v1/organizations/departments/tree/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]), 1)
        self.assertEqual(response.json()["data"][0]["children"][0]["dept_code"], "CHILD")
