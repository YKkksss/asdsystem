from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from apps.common.models import OperatorStampedModel, TimeStampedModel


class SecurityClearance(models.TextChoices):
    PUBLIC = "PUBLIC", "公开"
    INTERNAL = "INTERNAL", "内部"
    SECRET = "SECRET", "秘密"
    CONFIDENTIAL = "CONFIDENTIAL", "机密"
    TOP_SECRET = "TOP_SECRET", "绝密"


class DataScope(models.TextChoices):
    SELF = "SELF", "仅本人"
    DEPT = "DEPT", "本部门"
    DEPT_AND_CHILD = "DEPT_AND_CHILD", "本部门及子部门"
    ALL = "ALL", "全部"


class PermissionType(models.TextChoices):
    MENU = "MENU", "菜单"
    BUTTON = "BUTTON", "按钮"
    API = "API", "接口"


class SystemUserManager(BaseUserManager):
    def create_user(self, username: str, password: str | None = None, **extra_fields):
        if not username:
            raise ValueError("用户名不能为空。")

        password = password or extra_fields.pop("password", None)
        if not password:
            raise ValueError("密码不能为空。")

        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username: str, password: str, **extra_fields):
        extra_fields.setdefault("real_name", "系统管理员")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("status", True)

        if not extra_fields.get("dept"):
            raise ValueError("创建超级用户时必须指定所属部门。")

        user = self.create_user(username=username, password=password, **extra_fields)
        return user


class Role(OperatorStampedModel):
    role_code = models.CharField(max_length=64, unique=True, verbose_name="角色编码")
    role_name = models.CharField(max_length=100, verbose_name="角色名称")
    data_scope = models.CharField(
        max_length=32,
        choices=DataScope.choices,
        default=DataScope.SELF,
        verbose_name="数据权限范围",
    )
    status = models.BooleanField(default=True, db_index=True, verbose_name="是否启用")
    remark = models.CharField(max_length=255, null=True, blank=True, verbose_name="备注")
    permissions = models.ManyToManyField(
        "SystemPermission",
        through="RolePermission",
        related_name="roles",
        verbose_name="权限",
    )

    class Meta:
        db_table = "sys_role"
        ordering = ["id"]
        verbose_name = "角色"
        verbose_name_plural = "角色"

    def __str__(self) -> str:
        return f"{self.role_name}({self.role_code})"


class SystemPermission(TimeStampedModel):
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="上级权限",
    )
    permission_code = models.CharField(max_length=100, unique=True, verbose_name="权限编码")
    permission_name = models.CharField(max_length=100, verbose_name="权限名称")
    permission_type = models.CharField(
        max_length=32,
        choices=PermissionType.choices,
        default=PermissionType.MENU,
        verbose_name="权限类型",
    )
    module_name = models.CharField(max_length=64, db_index=True, verbose_name="模块名称")
    route_path = models.CharField(max_length=255, null=True, blank=True, verbose_name="路由路径")
    sort_order = models.IntegerField(default=0, verbose_name="排序值")
    status = models.BooleanField(default=True, db_index=True, verbose_name="是否启用")

    class Meta:
        db_table = "sys_permission"
        ordering = ["sort_order", "id"]
        verbose_name = "权限"
        verbose_name_plural = "权限"

    def __str__(self) -> str:
        return f"{self.permission_name}({self.permission_code})"


class SystemUser(AbstractBaseUser, PermissionsMixin, OperatorStampedModel):
    dept = models.ForeignKey(
        "organizations.Department",
        on_delete=models.PROTECT,
        related_name="users",
        db_column="dept_id",
        verbose_name="所属主部门",
    )
    username = models.CharField(max_length=64, unique=True, verbose_name="登录账号")
    real_name = models.CharField(max_length=100, db_index=True, verbose_name="真实姓名")
    email = models.EmailField(null=True, blank=True, db_index=True, verbose_name="邮箱")
    phone = models.CharField(max_length=32, null=True, blank=True, verbose_name="手机号")
    security_clearance_level = models.CharField(
        max_length=16,
        choices=SecurityClearance.choices,
        default=SecurityClearance.INTERNAL,
        db_index=True,
        verbose_name="最高密级",
    )
    status = models.BooleanField(default=True, db_index=True, verbose_name="是否启用")
    failed_login_count = models.PositiveIntegerField(default=0, verbose_name="连续失败次数")
    last_failed_login_at = models.DateTimeField(null=True, blank=True, verbose_name="最后失败时间")
    lock_until_at = models.DateTimeField(null=True, blank=True, verbose_name="锁定截止时间")
    last_login_at = models.DateTimeField(null=True, blank=True, verbose_name="最后登录时间")
    last_login_ip = models.CharField(max_length=64, null=True, blank=True, verbose_name="最后登录 IP")
    remark = models.CharField(max_length=255, null=True, blank=True, verbose_name="备注")
    is_staff = models.BooleanField(default=False, verbose_name="是否后台人员")
    roles = models.ManyToManyField(
        Role,
        through="UserRole",
        related_name="users",
        verbose_name="角色",
    )

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["real_name", "dept"]

    objects = SystemUserManager()

    class Meta:
        db_table = "sys_user"
        ordering = ["id"]
        verbose_name = "用户"
        verbose_name_plural = "用户"

    @property
    def is_active(self) -> bool:
        return self.status

    def __str__(self) -> str:
        return f"{self.real_name}({self.username})"


class UserRole(TimeStampedModel):
    user = models.ForeignKey(SystemUser, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_users")

    class Meta:
        db_table = "sys_user_role"
        constraints = [
            models.UniqueConstraint(fields=["user", "role"], name="uniq_user_role")
        ]
        verbose_name = "用户角色关联"
        verbose_name_plural = "用户角色关联"


class RolePermission(TimeStampedModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(
        SystemPermission,
        on_delete=models.CASCADE,
        related_name="permission_roles",
    )

    class Meta:
        db_table = "sys_role_permission"
        constraints = [
            models.UniqueConstraint(fields=["role", "permission"], name="uniq_role_permission")
        ]
        verbose_name = "角色权限关联"
        verbose_name_plural = "角色权限关联"
