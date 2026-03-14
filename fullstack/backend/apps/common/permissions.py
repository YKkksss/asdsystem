from rest_framework.permissions import BasePermission


def _has_any_role(user, role_codes: set[str]) -> bool:
    if not hasattr(user, "roles"):
        return False
    return user.roles.filter(role_code__in=role_codes, status=True).exists()


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
