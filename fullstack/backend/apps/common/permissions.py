import ipaddress

from rest_framework.permissions import BasePermission


def _has_any_role(user, role_codes: set[str]) -> bool:
    if not hasattr(user, "roles"):
        return False
    return user.roles.filter(role_code__in=role_codes, status=True).exists()


def _has_any_permission(user, permission_codes: set[str]) -> bool:
    if not hasattr(user, "roles"):
        return False
    return user.roles.filter(
        status=True,
        permissions__permission_code__in=permission_codes,
        permissions__status=True,
    ).exists()


def _resolve_configured_permissions(request, view) -> tuple[set[str], set[str]]:
    required_permission_codes = set(getattr(view, "required_permission_codes", ()) or ())
    fallback_roles = set(getattr(view, "permission_fallback_roles", ()) or ())

    action = getattr(view, "action", None)
    if action:
        action_permission_map = getattr(view, "action_required_permission_codes", {}) or {}
        action_fallback_map = getattr(view, "action_permission_fallback_roles", {}) or {}
        if action in action_permission_map:
            required_permission_codes = set(action_permission_map[action] or ())
        if action in action_fallback_map:
            fallback_roles = set(action_fallback_map[action] or ())

    method = request.method.upper()
    method_permission_map = getattr(view, "method_required_permission_codes", {}) or {}
    method_fallback_map = getattr(view, "method_permission_fallback_roles", {}) or {}
    if method in method_permission_map:
        required_permission_codes = set(method_permission_map[method] or ())
    if method in method_fallback_map:
        fallback_roles = set(method_fallback_map[method] or ())

    return required_permission_codes, fallback_roles


def _extract_client_ip(request) -> str | None:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
        if client_ip:
            return client_ip

    real_ip = request.META.get("HTTP_X_REAL_IP", "").strip()
    if real_ip:
        return real_ip

    remote_addr = request.META.get("REMOTE_ADDR", "").strip()
    return remote_addr or None


def _is_internal_request(request) -> bool:
    client_ip = _extract_client_ip(request)
    if not client_ip:
        return False

    try:
        ip_address = ipaddress.ip_address(client_ip)
    except ValueError:
        return False

    return ip_address.is_private or ip_address.is_loopback or ip_address.is_link_local


class IsSystemAdmin(BasePermission):
    message = "当前用户缺少管理员权限。"

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        if hasattr(user, "roles"):
            return _has_any_role(user, {"ADMIN"})
        return False


class IsArchiveManager(BasePermission):
    message = "当前用户缺少档案管理权限。"

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        return _has_any_role(user, {"ADMIN", "ARCHIVIST"})


class IsAuditViewer(BasePermission):
    message = "当前用户缺少审计查看权限。"

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        if _has_any_permission(user, {"menu.audit_log"}):
            return True
        return _has_any_role(user, {"ADMIN", "AUDITOR"})


class IsReportViewer(BasePermission):
    message = "当前用户缺少报表查看权限。"

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        if _has_any_permission(user, {"menu.report_center"}):
            return True
        return _has_any_role(user, {"ADMIN", "AUDITOR", "ARCHIVIST"})


class IsSystemAdminOrInternalRequest(BasePermission):
    message = "当前请求缺少管理员权限，且不在受信任的内网范围内。"

    def has_permission(self, request, view) -> bool:
        user = request.user
        if user and user.is_authenticated:
            if getattr(user, "is_superuser", False):
                return True
            if _has_any_role(user, {"ADMIN"}):
                return True

        return _is_internal_request(request)


class HasConfiguredSystemPermission(BasePermission):
    message = "当前用户缺少所需系统权限。"

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True

        required_permission_codes, fallback_roles = _resolve_configured_permissions(request, view)

        if required_permission_codes and _has_any_permission(user, required_permission_codes):
            return True

        if fallback_roles and _has_any_role(user, fallback_roles):
            return True

        return not required_permission_codes and not fallback_roles


class HasConfiguredSystemPermissionOrInternalRequest(BasePermission):
    message = "当前请求缺少所需系统权限，且不在受信任的内网范围内。"

    def has_permission(self, request, view) -> bool:
        user = request.user
        required_permission_codes, fallback_roles = _resolve_configured_permissions(request, view)

        if user and user.is_authenticated:
            if getattr(user, "is_superuser", False):
                return True

            if required_permission_codes and _has_any_permission(user, required_permission_codes):
                return True

            if fallback_roles and _has_any_role(user, fallback_roles):
                return True

            if not required_permission_codes and not fallback_roles:
                return True

        return _is_internal_request(request)
