from dataclasses import dataclass

from apps.accounts.models import DataScope, SecurityClearance


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


DEFAULT_ROLE_DEFINITIONS = [
    BootstrapRoleDefinition(role_code="ADMIN", role_name="管理员", data_scope=DataScope.ALL),
    BootstrapRoleDefinition(role_code="ARCHIVIST", role_name="档案员", data_scope=DataScope.DEPT),
    BootstrapRoleDefinition(role_code="BORROWER", role_name="借阅人", data_scope=DataScope.SELF),
    BootstrapRoleDefinition(role_code="AUDITOR", role_name="审计员", data_scope=DataScope.ALL),
]

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
