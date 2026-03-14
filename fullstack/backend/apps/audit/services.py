from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import ArchiveFileAccessAction, ArchiveFileAccessTicket, AuditLog, AuditResultStatus


def get_request_client_ip(request) -> str | None:
    if not request:
        return None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def record_audit_log(
    *,
    module_name: str,
    action_code: str,
    description: str,
    user=None,
    result_status: str = AuditResultStatus.SUCCESS,
    biz_type: str | None = None,
    biz_id: int | None = None,
    target_repr: str | None = None,
    request=None,
    extra_data: dict | None = None,
    username: str | None = None,
    real_name: str | None = None,
) -> AuditLog:
    user_obj = user if getattr(user, "is_authenticated", False) else None
    return AuditLog.objects.create(
        user=user_obj,
        username=username or getattr(user_obj, "username", "") or "",
        real_name=real_name or getattr(user_obj, "real_name", "") or "",
        module_name=module_name,
        action_code=action_code,
        biz_type=biz_type,
        biz_id=biz_id,
        target_repr=target_repr,
        result_status=result_status,
        description=description,
        ip_address=get_request_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255] if request else "",
        request_method=request.method if request else None,
        request_path=request.path[:255] if request else None,
        extra_data_json=extra_data or {},
    )


def build_watermark_text(user) -> str:
    display_name = getattr(user, "real_name", "") or getattr(user, "username", "") or "匿名用户"
    return f"{display_name} {timezone.now():%Y-%m-%d %H:%M}"


def issue_archive_file_access_ticket(
    *,
    archive_file,
    user,
    access_action: str,
    expires_at,
    purpose: str | None = None,
    watermark_text: str | None = None,
) -> ArchiveFileAccessTicket:
    return ArchiveFileAccessTicket.objects.create(
        archive_file=archive_file,
        user=user if getattr(user, "is_authenticated", False) else None,
        username=getattr(user, "username", "") or "",
        real_name=getattr(user, "real_name", "") or "",
        access_action=access_action,
        purpose=purpose,
        watermark_text=watermark_text,
        expires_at=expires_at,
    )


def validate_archive_file_access_ticket(*, token: str, access_action: str | None = None) -> ArchiveFileAccessTicket:
    ticket = (
        ArchiveFileAccessTicket.objects.select_related("archive_file", "archive_file__archive", "user")
        .filter(token=token, is_active=True)
        .first()
    )
    if not ticket:
        raise ValidationError("访问票据不存在或已失效。")
    if ticket.is_expired:
        ticket.is_active = False
        ticket.save(update_fields=["is_active", "updated_at"])
        raise ValidationError("访问票据已过期，请重新发起操作。")
    if access_action and ticket.access_action != access_action:
        raise ValidationError("访问票据类型不匹配。")
    if ticket.access_action == ArchiveFileAccessAction.DOWNLOAD and ticket.used_at:
        ticket.is_active = False
        ticket.save(update_fields=["is_active", "updated_at"])
        raise ValidationError("下载票据已使用，请重新申请。")
    return ticket


def mark_archive_file_access_ticket_used(*, ticket: ArchiveFileAccessTicket) -> ArchiveFileAccessTicket:
    ticket.access_count += 1
    ticket.last_accessed_at = timezone.now()
    update_fields = ["access_count", "last_accessed_at", "updated_at"]
    if ticket.access_action == ArchiveFileAccessAction.DOWNLOAD:
        ticket.used_at = ticket.last_accessed_at
        ticket.is_active = False
        update_fields.extend(["used_at", "is_active"])
    ticket.save(update_fields=update_fields)
    return ticket


def build_audit_summary() -> dict:
    today = timezone.localdate()
    total_count = AuditLog.objects.count()
    today_count = AuditLog.objects.filter(created_at__date=today).count()
    failed_count = AuditLog.objects.filter(result_status__in=[AuditResultStatus.FAILED, AuditResultStatus.DENIED]).count()
    preview_count = AuditLog.objects.filter(action_code__in=["ARCHIVE_FILE_PREVIEW_APPLY", "ARCHIVE_FILE_PREVIEW_ACCESS"]).count()
    download_count = AuditLog.objects.filter(action_code__in=["ARCHIVE_FILE_DOWNLOAD_APPLY", "ARCHIVE_FILE_DOWNLOAD_ACCESS"]).count()
    module_counts = list(
        AuditLog.objects.values("module_name")
        .annotate(count=Count("id"))
        .order_by("-count", "module_name")[:5]
    )
    return {
        "total_count": total_count,
        "today_count": today_count,
        "failed_count": failed_count,
        "preview_count": preview_count,
        "download_count": download_count,
        "module_counts": module_counts,
    }

