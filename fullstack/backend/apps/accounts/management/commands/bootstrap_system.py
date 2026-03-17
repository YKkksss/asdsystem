from dataclasses import replace
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.bootstrap_defaults import (
    DEFAULT_CHILD_DEPARTMENTS,
    DEFAULT_PERMISSION_DEFINITIONS,
    DEFAULT_ROLE_DEFINITIONS,
    DEFAULT_ROLE_PERMISSION_CODES,
    BootstrapDepartmentDefinition,
    BootstrapPermissionDefinition,
    BootstrapUserDefinition,
    build_default_users,
    render_account_markdown,
)
from apps.accounts.models import Role, SystemPermission
from apps.accounts.services import assign_permissions_to_role, assign_roles_to_user
from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class Command(BaseCommand):
    help = "初始化根部门、基础角色、默认示例账号，并生成账号清单文件。"

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="管理员登录账号")
        parser.add_argument("--password", required=True, help="管理员登录密码")
        parser.add_argument("--real-name", default="系统管理员", help="管理员姓名")
        parser.add_argument("--dept-code", default="ROOT", help="根部门编码")
        parser.add_argument("--dept-name", default="总部", help="根部门名称")
        parser.add_argument(
            "--account-file",
            default=str(settings.BASE_DIR.parent / "runtime" / "deployment_runtime" / "accounts.md"),
            help="账号清单输出文件路径，默认生成到 fullstack/runtime/deployment_runtime/ 目录。",
        )
        parser.add_argument(
            "--preserve-existing-passwords",
            action="store_true",
            help="如果用户已存在，则保留现有密码不重置，仅同步角色、部门和其他基础属性。",
        )

    def _upsert_department(self, definition: BootstrapDepartmentDefinition, department_map: dict[str, Department]) -> Department:
        parent = department_map.get(definition.parent_code) if definition.parent_code else None
        department, _ = Department.objects.get_or_create(
            dept_code=definition.dept_code,
            defaults={
                "dept_name": definition.dept_name,
                "parent": parent,
                "status": True,
            },
        )
        department.dept_name = definition.dept_name
        department.parent = parent
        department.status = True
        department.save()
        sync_department_hierarchy(department)
        department_map[definition.dept_code] = department
        return department

    def _upsert_role_map(self) -> dict[str, Role]:
        role_map: dict[str, Role] = {}
        for definition in DEFAULT_ROLE_DEFINITIONS:
            role, _ = Role.objects.get_or_create(
                role_code=definition.role_code,
                defaults={
                    "role_name": definition.role_name,
                    "data_scope": definition.data_scope,
                    "status": True,
                },
            )
            role.role_name = definition.role_name
            role.data_scope = definition.data_scope
            role.status = True
            role.save()
            role_map[definition.role_code] = role
        return role_map

    def _upsert_permission_map(self) -> dict[str, SystemPermission]:
        permission_map: dict[str, SystemPermission] = {}
        for definition in DEFAULT_PERMISSION_DEFINITIONS:
            permission, _ = SystemPermission.objects.get_or_create(
                permission_code=definition.permission_code,
                defaults={
                    "permission_name": definition.permission_name,
                    "permission_type": definition.permission_type,
                    "module_name": definition.module_name,
                    "route_path": definition.route_path,
                    "sort_order": definition.sort_order,
                    "status": True,
                },
            )
            permission.permission_name = definition.permission_name
            permission.permission_type = definition.permission_type
            permission.module_name = definition.module_name
            permission.route_path = definition.route_path
            permission.sort_order = definition.sort_order
            permission.status = True
            permission.parent = None
            permission.save()
            permission_map[definition.permission_code] = permission
        return permission_map

    def _bind_role_permissions(
        self,
        *,
        role_map: dict[str, Role],
        permission_map: dict[str, SystemPermission],
    ) -> None:
        for role_code, role in role_map.items():
            permission_codes = DEFAULT_ROLE_PERMISSION_CODES.get(role_code, ())
            permission_ids = [
                permission_map[permission_code].id
                for permission_code in permission_codes
                if permission_code in permission_map
            ]
            assign_permissions_to_role(role, permission_ids)

    def _upsert_user(
        self,
        *,
        definition: BootstrapUserDefinition,
        role_map: dict[str, Role],
        department_map: dict[str, Department],
        preserve_existing_passwords: bool,
    ) -> tuple[User, BootstrapUserDefinition]:
        department = department_map[definition.dept_code]
        user, created = User.objects.get_or_create(
            username=definition.username,
            defaults={
                "real_name": definition.real_name,
                "dept": department,
                "is_staff": definition.is_staff,
                "status": True,
                "security_clearance_level": definition.security_clearance_level,
            },
        )

        user.real_name = definition.real_name
        user.dept = department
        user.is_staff = definition.is_staff
        user.status = True
        user.security_clearance_level = definition.security_clearance_level
        account_definition = definition
        if created or not preserve_existing_passwords:
            user.set_password(definition.password)
        else:
            account_definition = replace(definition, password="沿用已有密码")
        user.save()
        assign_roles_to_user(user, [role_map[definition.role_code].id])
        return user, account_definition

    def _write_account_file(self, *, dept_name: str, account_file: Path, users: list[BootstrapUserDefinition]) -> None:
        account_file.parent.mkdir(parents=True, exist_ok=True)
        account_file.write_text(
            render_account_markdown(dept_name=dept_name, accounts=users),
            encoding="utf-8",
        )

    def handle(self, *args, **options):
        username = options["username"].strip()
        password = options["password"]
        real_name = options["real_name"].strip()
        dept_code = options["dept_code"].strip()
        dept_name = options["dept_name"].strip()
        account_file = Path(options["account_file"]).expanduser().resolve()
        preserve_existing_passwords = bool(options["preserve_existing_passwords"])

        if len(password) < 6:
            raise CommandError("管理员密码长度不能少于 6 位。")

        department_map: dict[str, Department] = {}
        root_definition = BootstrapDepartmentDefinition(dept_code=dept_code, dept_name=dept_name)
        root_department = self._upsert_department(root_definition, department_map)
        department_map["ROOT"] = root_department

        for definition in DEFAULT_CHILD_DEPARTMENTS:
            self._upsert_department(definition, department_map)

        role_map = self._upsert_role_map()
        permission_map = self._upsert_permission_map()
        self._bind_role_permissions(role_map=role_map, permission_map=permission_map)
        user_definitions = build_default_users(
            admin_username=username,
            admin_password=password,
            admin_real_name=real_name,
            root_dept_code=dept_code,
        )

        user_map: dict[str, User] = {}
        account_user_definitions: list[BootstrapUserDefinition] = []
        for definition in user_definitions:
            user, account_definition = self._upsert_user(
                definition=definition,
                role_map=role_map,
                department_map=department_map,
                preserve_existing_passwords=preserve_existing_passwords,
            )
            user_map[definition.role_code] = user
            account_user_definitions.append(account_definition)

        admin_user = user_map["ADMIN"]
        for department in department_map.values():
            if department.approver_user_id != admin_user.id:
                department.approver_user_id = admin_user.id
                department.save(update_fields=["approver_user_id", "updated_at"])

        self._write_account_file(
            dept_name=dept_name,
            account_file=account_file,
            users=account_user_definitions,
        )

        self.stdout.write(self.style.SUCCESS(f"初始化账号完成，共写入 {len(user_definitions)} 个角色账号。"))
        self.stdout.write(self.style.SUCCESS(f"账号清单文件已生成：{account_file}"))
