import ipaddress

from rest_framework.permissions import BasePermission


def _has_any_role(user, role_codes: set[str]) -> bool:
    if not hasattr(user, "roles"):
        return False
    return user.roles.filter(role_code__in=role_codes, status=True).exists()


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
        return _has_any_role(user, {"ADMIN", "AUDITOR"})


class IsReportViewer(BasePermission):
    message = "当前用户缺少报表查看权限。"

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
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
