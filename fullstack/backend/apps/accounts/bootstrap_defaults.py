from dataclasses import dataclass

from apps.accounts.models import DataScope, PermissionType, SecurityClearance


@dataclass(frozen=True)
class BootstrapRoleDefinition:
    role_code: str
    role_name: str
    data_scope: str


@dataclass(frozen=True)
class BootstrapDepartmentDefinition:
    dept_code: str
    dept_name: str
    parent_code: str | None = None


@dataclass(frozen=True)
class BootstrapUserDefinition:
    username: str
    password: str
    real_name: str
    role_code: str
    dept_code: str
    is_staff: bool
    security_clearance_level: str
    remark: str


@dataclass(frozen=True)
class BootstrapPermissionDefinition:
    permission_code: str
    permission_name: str
    permission_type: str
    module_name: str
    route_path: str | None
    sort_order: int


MENU_PERMISSION_DEFINITIONS = [
    BootstrapPermissionDefinition(
        permission_code="menu.dashboard",
        permission_name="工作台",
        permission_type=PermissionType.MENU,
        module_name="dashboard",
        route_path="/",
        sort_order=10,
    ),
    BootstrapPermissionDefinition(
        permission_code="menu.archive_center",
        permission_name="档案中心",
        permission_type=PermissionType.MENU,
        module_name="archives",
        route_path="/archives/records",
        sort_order=20,
    ),
    BootstrapPermissionDefinition(
        permission_code="menu.archive_location",
        permission_name="实体位置",
        permission_type=PermissionType.MENU,
        module_name="archives",
        route_path="/archives/locations",
        sort_order=30,
    ),
    BootstrapPermissionDefinition(
        permission_code="menu.scan_task",
        permission_name="数字化任务",
        permission_type=PermissionType.MENU,
        module_name="digitization",
        route_path="/digitization/scan-tasks",
        sort_order=40,
    ),
    BootstrapPermissionDefinition(
        permission_code="menu.borrow_center",
        permission_name="借阅中心",
        permission_type=PermissionType.MENU,
        module_name="borrowing",
        route_path="/borrowing/applications",
        sort_order=50,
    ),
    BootstrapPermissionDefinition(
        permission_code="menu.borrow_approval",
        permission_name="借阅审批",
        permission_type=PermissionType.MENU,
        module_name="borrowing",
        route_path="/borrowing/approvals",
        sort_order=60,
    ),
    BootstrapPermissionDefinition(
        permission_code="menu.borrow_checkout",
        permission_name="出库登记",
        permission_type=PermissionType.MENU,
        module_name="borrowing",
        route_path="/borrowing/checkout",
        sort_order=70,
    ),
    BootstrapPermissionDefinition(
        permission_code="menu.borrow_return",
        permission_name="归还中心",
        permission_type=PermissionType.MENU,
        module_name="borrowing",
        route_path="/borrowing/returns",
        sort_order=80,
    ),
    BootstrapPermissionDefinition(
        permission_code="menu.notification_center",
        permission_name="通知中心",
        permission_type=PermissionType.MENU,
        module_name="notifications",
        route_path="/notifications/messages",
        sort_order=90,
    ),
    BootstrapPermissionDefinition(
        permission_code="menu.destruction_center",
        permission_name="销毁中心",
        permission_type=PermissionType.MENU,
        module_name="destruction",
        route_path="/destruction/applications",
        sort_order=100,
    ),
    BootstrapPermissionDefinition(
        permission_code="menu.report_center",
        permission_name="报表中心",
        permission_type=PermissionType.MENU,
        module_name="reports",
        route_path="/reports/center",
        sort_order=110,
    ),
    BootstrapPermissionDefinition(
        permission_code="menu.audit_log",
        permission_name="审计日志",
        permission_type=PermissionType.MENU,
        module_name="audit",
        route_path="/audit/logs",
        sort_order=120,
    ),
    BootstrapPermissionDefinition(
        permission_code="menu.system_management",
        permission_name="系统管理",
        permission_type=PermissionType.MENU,
        module_name="system",
        route_path="/system/management",
        sort_order=130,
    ),
]

BUTTON_PERMISSION_DEFINITIONS = [
    BootstrapPermissionDefinition(
        permission_code="button.archive.create",
        permission_name="新建档案",
        permission_type=PermissionType.BUTTON,
        module_name="archives",
        route_path=None,
        sort_order=210,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.archive.edit",
        permission_name="编辑档案",
        permission_type=PermissionType.BUTTON,
        module_name="archives",
        route_path=None,
        sort_order=220,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.archive.transition",
        permission_name="流转档案状态",
        permission_type=PermissionType.BUTTON,
        module_name="archives",
        route_path=None,
        sort_order=230,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.archive.generate_code",
        permission_name="生成档案条码",
        permission_type=PermissionType.BUTTON,
        module_name="archives",
        route_path=None,
        sort_order=240,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.archive.print",
        permission_name="打印档案标签",
        permission_type=PermissionType.BUTTON,
        module_name="archives",
        route_path=None,
        sort_order=250,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.location.manage",
        permission_name="维护实体位置",
        permission_type=PermissionType.BUTTON,
        module_name="archives",
        route_path=None,
        sort_order=260,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.scan_task.manage",
        permission_name="维护数字化任务",
        permission_type=PermissionType.BUTTON,
        module_name="digitization",
        route_path=None,
        sort_order=270,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.borrow.create",
        permission_name="提交借阅申请",
        permission_type=PermissionType.BUTTON,
        module_name="borrowing",
        route_path=None,
        sort_order=280,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.borrow.approve",
        permission_name="审批借阅申请",
        permission_type=PermissionType.BUTTON,
        module_name="borrowing",
        route_path=None,
        sort_order=290,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.borrow.checkout",
        permission_name="办理借阅出库",
        permission_type=PermissionType.BUTTON,
        module_name="borrowing",
        route_path=None,
        sort_order=300,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.borrow.return.submit",
        permission_name="提交档案归还",
        permission_type=PermissionType.BUTTON,
        module_name="borrowing",
        route_path=None,
        sort_order=310,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.borrow.return.confirm",
        permission_name="确认档案归还",
        permission_type=PermissionType.BUTTON,
        module_name="borrowing",
        route_path=None,
        sort_order=320,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.notification.reminder.dispatch",
        permission_name="执行催还扫描",
        permission_type=PermissionType.BUTTON,
        module_name="notifications",
        route_path=None,
        sort_order=325,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.destruction.create",
        permission_name="发起销毁申请",
        permission_type=PermissionType.BUTTON,
        module_name="destruction",
        route_path=None,
        sort_order=330,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.destruction.approve",
        permission_name="审批销毁申请",
        permission_type=PermissionType.BUTTON,
        module_name="destruction",
        route_path=None,
        sort_order=340,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.destruction.execute",
        permission_name="执行档案销毁",
        permission_type=PermissionType.BUTTON,
        module_name="destruction",
        route_path=None,
        sort_order=350,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.system.user.manage",
        permission_name="维护用户",
        permission_type=PermissionType.BUTTON,
        module_name="system",
        route_path=None,
        sort_order=360,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.system.role.manage",
        permission_name="维护角色",
        permission_type=PermissionType.BUTTON,
        module_name="system",
        route_path=None,
        sort_order=370,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.system.permission.manage",
        permission_name="维护权限项",
        permission_type=PermissionType.BUTTON,
        module_name="system",
        route_path=None,
        sort_order=380,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.system.department.manage",
        permission_name="维护组织架构",
        permission_type=PermissionType.BUTTON,
        module_name="system",
        route_path=None,
        sort_order=390,
    ),
    BootstrapPermissionDefinition(
        permission_code="button.system.health.detail",
        permission_name="查看系统健康详情",
        permission_type=PermissionType.BUTTON,
        module_name="system",
        route_path=None,
        sort_order=395,
    ),
]

DEFAULT_PERMISSION_DEFINITIONS = MENU_PERMISSION_DEFINITIONS + BUTTON_PERMISSION_DEFINITIONS

DEFAULT_ROLE_PERMISSION_CODES: dict[str, tuple[str, ...]] = {
    "ADMIN": tuple(item.permission_code for item in DEFAULT_PERMISSION_DEFINITIONS),
    "ARCHIVIST": (
        "menu.dashboard",
        "menu.archive_center",
        "menu.archive_location",
        "menu.scan_task",
        "menu.borrow_center",
        "menu.borrow_checkout",
        "menu.borrow_return",
        "menu.notification_center",
        "menu.destruction_center",
        "menu.report_center",
        "button.archive.create",
        "button.archive.edit",
        "button.archive.transition",
        "button.archive.generate_code",
        "button.archive.print",
        "button.location.manage",
        "button.scan_task.manage",
        "button.borrow.checkout",
        "button.borrow.return.confirm",
        "button.notification.reminder.dispatch",
        "button.destruction.create",
        "button.destruction.execute",
    ),
    "BORROWER": (
        "menu.dashboard",
        "menu.borrow_center",
        "menu.borrow_return",
        "menu.notification_center",
        "button.borrow.create",
        "button.borrow.return.submit",
    ),
    "AUDITOR": (
        "menu.dashboard",
        "menu.notification_center",
        "menu.report_center",
        "menu.audit_log",
    ),
}


DEFAULT_ROLE_DEFINITIONS = [
    BootstrapRoleDefinition(role_code="ADMIN", role_name="管理员", data_scope=DataScope.ALL),
    BootstrapRoleDefinition(role_code="ARCHIVIST", role_name="档案员", data_scope=DataScope.DEPT),
    BootstrapRoleDefinition(role_code="BORROWER", role_name="借阅人", data_scope=DataScope.SELF),
    BootstrapRoleDefinition(role_code="AUDITOR", role_name="审计员", data_scope=DataScope.ALL),
]

DEFAULT_ROLE_TEMPLATE_DESCRIPTIONS: dict[str, str] = {
    "ADMIN": "适用于系统总管理员，默认拥有全部菜单、按钮和系统配置权限。",
    "ARCHIVIST": "适用于档案员，覆盖建档、上架、数字化、归还验收和催还扫描等日常档案管理动作。",
    "BORROWER": "适用于借阅人，聚焦工作台、借阅申请、归还提交通知查看等个人操作。",
    "AUDITOR": "适用于审计与监管角色，聚焦工作台、通知、报表和审计日志等监督类只读能力。",
}


def build_default_role_permission_templates() -> list[dict[str, object]]:
    role_name_map = {item.role_code: item.role_name for item in DEFAULT_ROLE_DEFINITIONS}
    templates: list[dict[str, object]] = []

    for role_definition in DEFAULT_ROLE_DEFINITIONS:
        permission_codes = list(DEFAULT_ROLE_PERMISSION_CODES.get(role_definition.role_code, ()))
        templates.append(
            {
                "template_key": role_definition.role_code,
                "role_code": role_definition.role_code,
                "role_name": role_name_map[role_definition.role_code],
                "template_name": f"{role_name_map[role_definition.role_code]}默认模板",
                "description": DEFAULT_ROLE_TEMPLATE_DESCRIPTIONS.get(role_definition.role_code, ""),
                "permission_codes": permission_codes,
            }
        )

    return templates

DEFAULT_CHILD_DEPARTMENTS = [
    BootstrapDepartmentDefinition(dept_code="ARC", dept_name="档案室", parent_code="ROOT"),
    BootstrapDepartmentDefinition(dept_code="BUS", dept_name="业务部", parent_code="ROOT"),
    BootstrapDepartmentDefinition(dept_code="AUD", dept_name="审计部", parent_code="ROOT"),
]


def build_default_users(
    *,
    admin_username: str,
    admin_password: str,
    admin_real_name: str,
    root_dept_code: str,
) -> list[BootstrapUserDefinition]:
    return [
        BootstrapUserDefinition(
            username=admin_username,
            password=admin_password,
            real_name=admin_real_name,
            role_code="ADMIN",
            dept_code=root_dept_code,
            is_staff=True,
            security_clearance_level=SecurityClearance.TOP_SECRET,
            remark="系统初始化管理员账号，负责系统配置与审批兜底。",
        ),
        BootstrapUserDefinition(
            username="archivist",
            password="Archivist12345",
            real_name="档案员示例账号",
            role_code="ARCHIVIST",
            dept_code="ARC",
            is_staff=True,
            security_clearance_level=SecurityClearance.SECRET,
            remark="档案管理、扫描任务、出入库与销毁流程使用。",
        ),
        BootstrapUserDefinition(
            username="borrower",
            password="Borrower12345",
            real_name="借阅人示例账号",
            role_code="BORROWER",
            dept_code="BUS",
            is_staff=False,
            security_clearance_level=SecurityClearance.INTERNAL,
            remark="借阅申请、归还、通知查看等普通业务使用。",
        ),
        BootstrapUserDefinition(
            username="auditor",
            password="Auditor12345",
            real_name="审计员示例账号",
            role_code="AUDITOR",
            dept_code="AUD",
            is_staff=True,
            security_clearance_level=SecurityClearance.CONFIDENTIAL,
            remark="审计日志与报表查看使用。",
        ),
    ]


def render_account_markdown(*, dept_name: str, accounts: list[BootstrapUserDefinition]) -> str:
    lines = [
        "# 初始化账号清单",
        "",
        "> 该文件由 `bootstrap_system` 初始化命令生成，请勿在生产环境直接使用以下默认密码。",
        "",
        f"- 根部门：{dept_name}",
        f"- 账号数量：{len(accounts)}",
        "",
        "| 角色 | 用户名 | 密码 | 部门编码 | 说明 |",
        "| --- | --- | --- | --- | --- |",
    ]

    role_name_map = {item.role_code: item.role_name for item in DEFAULT_ROLE_DEFINITIONS}
    for account in accounts:
        lines.append(
            f"| {role_name_map.get(account.role_code, account.role_code)} | "
            f"{account.username} | {account.password} | {account.dept_code} | {account.remark} |"
        )

    lines.extend(
        [
            "",
            "## 使用说明",
            "",
            "- 初始化命令可重复执行，重复执行会同步更新上述账号密码与角色绑定。",
            "- 如果需要修改默认账号，请调整 `fullstack/backend/apps/accounts/bootstrap_defaults.py` 后重新执行初始化命令。",
        ]
    )
    return "\n".join(lines) + "\n"
