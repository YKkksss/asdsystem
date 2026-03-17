from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.accounts.bootstrap_defaults import (
    DEFAULT_CHILD_DEPARTMENTS,
    DEFAULT_PERMISSION_DEFINITIONS,
    DEFAULT_ROLE_DEFINITIONS,
    build_default_users,
)
from apps.accounts.models import Role, SystemPermission, UserRole
from apps.organizations.models import Department


User = get_user_model()


class Command(BaseCommand):
    help = "检查基础引导数据是否已就绪，用于部署脚本判断是否需要执行 bootstrap_system。"

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="管理员登录账号")
        parser.add_argument("--dept-code", default="ROOT", help="根部门编码")
        parser.add_argument(
            "--account-file",
            default="",
            help="账号清单文件路径；如果文件缺失，也会被判定为需要执行基础同步。",
        )

    def handle(self, *args, **options):
        admin_username = options["username"].strip()
        root_dept_code = options["dept_code"].strip()
        account_file = options["account_file"].strip()

        missing_items: list[str] = []

        if not Department.objects.filter(dept_code=root_dept_code).exists():
            missing_items.append(f"DEPARTMENT:{root_dept_code}")

        for department_definition in DEFAULT_CHILD_DEPARTMENTS:
            if not Department.objects.filter(dept_code=department_definition.dept_code).exists():
                missing_items.append(f"DEPARTMENT:{department_definition.dept_code}")

        for role_definition in DEFAULT_ROLE_DEFINITIONS:
            if not Role.objects.filter(role_code=role_definition.role_code, status=True).exists():
                missing_items.append(f"ROLE:{role_definition.role_code}")

        for permission_definition in DEFAULT_PERMISSION_DEFINITIONS:
            if not SystemPermission.objects.filter(
                permission_code=permission_definition.permission_code,
                status=True,
            ).exists():
                missing_items.append(f"PERMISSION:{permission_definition.permission_code}")

        expected_users = build_default_users(
            admin_username=admin_username,
            admin_password="placeholder",
            admin_real_name="系统管理员",
            root_dept_code=root_dept_code,
        )
        for user_definition in expected_users:
            user = User.objects.filter(username=user_definition.username, status=True).first()
            if not user:
                missing_items.append(f"USER:{user_definition.username}")
                continue
            if not UserRole.objects.filter(
                user=user,
                role__role_code=user_definition.role_code,
                role__status=True,
            ).exists():
                missing_items.append(f"USER_ROLE:{user_definition.username}:{user_definition.role_code}")

        if account_file and not Path(account_file).exists():
            missing_items.append("ACCOUNT_FILE")

        bootstrap_required = bool(missing_items)
        self.stdout.write(f"BOOTSTRAP_REQUIRED={'true' if bootstrap_required else 'false'}")
        if missing_items:
            self.stdout.write(f"BOOTSTRAP_REASONS={','.join(missing_items)}")
