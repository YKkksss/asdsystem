from datetime import timedelta
import logging

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, AuthenticationFailed, PermissionDenied
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.audit.models import AuditResultStatus
from apps.audit.services import record_audit_log
from apps.accounts.models import Role, RolePermission, SystemPermission, UserRole
from apps.notifications.models import NotificationType
from apps.notifications.services import create_system_notification


logger = logging.getLogger(__name__)
User = get_user_model()

LOGIN_FAIL_LIMIT = 3
LOCK_MINUTES = 15


class RefreshTokenInvalid(APIException):
    status_code = 401
    default_detail = "刷新令牌无效或已过期。"
    default_code = "refresh_token_invalid"


def _login_fail_key(username: str) -> str:
    return f"auth:login_fail:{username}"


def _user_lock_key(user_id: int) -> str:
    return f"auth:user_lock:{user_id}"


def get_locked_until(user: User):
    cached_lock_until = cache.get(_user_lock_key(user.id))
    if cached_lock_until:
        return timezone.datetime.fromisoformat(cached_lock_until)
    if user.lock_until_at and user.lock_until_at > timezone.now():
        return user.lock_until_at
    return None


def clear_login_fail_state(user: User) -> None:
    cache.delete(_login_fail_key(user.username))
    cache.delete(_user_lock_key(user.id))

    user.failed_login_count = 0
    user.last_failed_login_at = None
    user.lock_until_at = None
    user.save(update_fields=["failed_login_count", "last_failed_login_at", "lock_until_at", "updated_at"])


def register_login_failure(user: User, request=None) -> tuple[int, timezone.datetime | None]:
    fail_key = _login_fail_key(user.username)
    next_fail_count = int(cache.get(fail_key, user.failed_login_count)) + 1
    cache.set(fail_key, next_fail_count, timeout=LOCK_MINUTES * 60)

    lock_until = None
    if next_fail_count >= LOGIN_FAIL_LIMIT:
        lock_until = timezone.now() + timedelta(minutes=LOCK_MINUTES)
        cache.set(_user_lock_key(user.id), lock_until.isoformat(), timeout=LOCK_MINUTES * 60)

    user.failed_login_count = next_fail_count
    user.last_failed_login_at = timezone.now()
    user.lock_until_at = lock_until
    user.save(update_fields=["failed_login_count", "last_failed_login_at", "lock_until_at", "updated_at"])

    logger.warning("用户登录失败", extra={"username": user.username, "failed_count": next_fail_count})
    record_audit_log(
        module_name="AUTH",
        action_code="LOGIN_LOCKED" if lock_until else "LOGIN_FAILED",
        description="用户登录失败，账号已锁定 15 分钟。" if lock_until else "用户登录失败，密码校验未通过。",
        user=user,
        result_status=AuditResultStatus.DENIED if lock_until else AuditResultStatus.FAILED,
        biz_type="system_user",
        biz_id=user.id,
        target_repr=user.username,
        request=request,
        extra_data={
            "failed_login_count": next_fail_count,
            "lock_until_at": lock_until.isoformat() if lock_until else None,
        },
    )
    return next_fail_count, lock_until


def complete_login_success(user: User, request_ip: str | None, request=None) -> dict:
    clear_login_fail_state(user)
    user.last_login_at = timezone.now()
    user.last_login_ip = request_ip
    user.save(update_fields=["last_login_at", "last_login_ip", "updated_at"])

    refresh = RefreshToken.for_user(user)

    logger.info("用户登录成功", extra={"username": user.username, "user_id": user.id})
    record_audit_log(
        module_name="AUTH",
        action_code="LOGIN_SUCCESS",
        description="用户登录成功并签发访问令牌。",
        user=user,
        biz_type="system_user",
        biz_id=user.id,
        target_repr=user.username,
        request=request,
        extra_data={"request_ip": request_ip},
    )

    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


def refresh_access_token(refresh_token: str, request=None) -> dict:
    try:
        refresh = RefreshToken(refresh_token)
    except TokenError as exc:
        logger.warning("刷新访问令牌失败，刷新令牌无效", extra={"error": str(exc)})
        record_audit_log(
            module_name="AUTH",
            action_code="TOKEN_REFRESH_FAILED",
            description="刷新访问令牌失败，刷新令牌无效或已过期。",
            result_status=AuditResultStatus.FAILED,
            request=request,
        )
        raise RefreshTokenInvalid() from exc

    user_id = refresh.payload.get("user_id")
    user = User.objects.select_related("dept").filter(id=user_id).first()
    if not user:
        logger.warning("刷新访问令牌失败，用户不存在", extra={"user_id": user_id})
        record_audit_log(
            module_name="AUTH",
            action_code="TOKEN_REFRESH_FAILED",
            description="刷新访问令牌失败，刷新令牌对应用户不存在。",
            result_status=AuditResultStatus.FAILED,
            biz_type="system_user",
            biz_id=user_id,
            target_repr=str(user_id),
            request=request,
        )
        raise RefreshTokenInvalid("刷新令牌无效或对应用户不存在。")

    if not user.status:
        logger.warning("刷新访问令牌失败，用户已停用", extra={"user_id": user.id, "username": user.username})
        record_audit_log(
            module_name="AUTH",
            action_code="TOKEN_REFRESH_DENIED",
            description="刷新访问令牌被拒绝，账号已停用。",
            user=user,
            result_status=AuditResultStatus.DENIED,
            biz_type="system_user",
            biz_id=user.id,
            target_repr=user.username,
            request=request,
        )
        raise PermissionDenied("当前账号已停用，请重新登录。")

    access_token = str(refresh.access_token)
    logger.info("刷新访问令牌成功", extra={"user_id": user.id, "username": user.username})
    record_audit_log(
        module_name="AUTH",
        action_code="TOKEN_REFRESH",
        description="用户使用刷新令牌续签访问令牌。",
        user=user,
        biz_type="system_user",
        biz_id=user.id,
        target_repr=user.username,
        request=request,
    )
    return {"access": access_token}


def build_user_profile(user: User) -> dict:
    roles = list(user.roles.filter(status=True).values("id", "role_code", "role_name", "data_scope"))
    permissions = list(
        SystemPermission.objects.filter(
            permission_roles__role__users=user,
            permission_roles__role__status=True,
            status=True,
        )
        .distinct()
        .values("id", "permission_code", "permission_name", "permission_type", "module_name", "route_path")
    )
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "email": user.email,
        "phone": user.phone,
        "dept_id": user.dept_id,
        "dept_name": user.dept.dept_name,
        "security_clearance_level": user.security_clearance_level,
        "status": user.status,
        "roles": roles,
        "permissions": permissions,
    }


@transaction.atomic
def assign_roles_to_user(user: User, role_ids: list[int]) -> None:
    UserRole.objects.filter(user=user).delete()
    if not role_ids:
        return
    user_roles = [UserRole(user=user, role_id=role_id) for role_id in set(role_ids)]
    UserRole.objects.bulk_create(user_roles)


@transaction.atomic
def assign_permissions_to_role(role: Role, permission_ids: list[int]) -> None:
    RolePermission.objects.filter(role=role).delete()
    if not permission_ids:
        return
    role_permissions = [
        RolePermission(role=role, permission_id=permission_id)
        for permission_id in set(permission_ids)
    ]
    RolePermission.objects.bulk_create(role_permissions)


def unlock_user(user: User, operator=None, request=None) -> None:
    clear_login_fail_state(user)
    logger.info("管理员解锁用户", extra={"username": user.username, "user_id": user.id})
    record_audit_log(
        module_name="AUTH",
        action_code="USER_UNLOCK",
        description="管理员手工解锁用户账号。",
        user=operator,
        biz_type="system_user",
        biz_id=user.id,
        target_repr=user.username,
        request=request,
    )
    operator_name = getattr(operator, "real_name", "") or getattr(operator, "username", "") or "管理员"
    create_system_notification(
        user=user,
        notification_type=NotificationType.SYSTEM,
        title="账号已解锁",
        content=f"{operator_name} 已为你解除登录锁定，请重新使用当前账号登录系统。",
    )
