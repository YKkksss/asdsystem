import logging
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.archives.models import ArchiveFile
from apps.digitization.models import ScanTaskItem
from apps.notifications.models import EmailTask, EmailTaskStatus, NotificationType, SystemNotification


logger = logging.getLogger(__name__)


LOCAL_ONLY_EMAIL_BACKENDS = {
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.filebased.EmailBackend",
    "django.core.mail.backends.locmem.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
}


def _mask_segment(value: str) -> str:
    if not value:
        return "***"
    if len(value) == 1:
        return f"{value}***"
    return f"{value[0]}***{value[-1]}"


def mask_email_address(email: str) -> str:
    local_part, separator, domain_part = email.partition("@")
    if not separator or not local_part or not domain_part:
        return "***"

    domain_name, domain_separator, domain_suffix = domain_part.partition(".")
    masked_domain = _mask_segment(domain_name)
    if domain_separator and domain_suffix:
        masked_domain = f"{masked_domain}.{domain_suffix}"

    return f"{_mask_segment(local_part)}@{masked_domain}"


def mask_webhook_url(webhook_url: str) -> str:
    parsed = urlsplit(webhook_url)
    if not parsed.scheme or not parsed.netloc:
        return "***"

    host = parsed.hostname or parsed.netloc
    host_parts = [part for part in host.split(".") if part]
    if not host_parts:
        return "***"

    if len(host_parts) == 1:
        masked_host = _mask_segment(host_parts[0])
    else:
        masked_host = ".".join([_mask_segment(part) for part in host_parts[:-1]] + [host_parts[-1]])

    port_part = f":{parsed.port}" if parsed.port else ""
    path_part = "/***" if parsed.path and parsed.path != "/" else ""
    if parsed.query:
        path_part = path_part or "/***"

    return f"{parsed.scheme}://{masked_host}{port_part}{path_part}"


@transaction.atomic
def create_system_notification(
    *,
    user,
    notification_type: str,
    title: str,
    content: str,
    biz_type: str | None = None,
    biz_id: int | None = None,
) -> SystemNotification:
    notification = SystemNotification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title,
        content=content,
        biz_type=biz_type,
        biz_id=biz_id,
    )
    logger.info(
        "创建站内通知",
        extra={
            "notification_id": notification.id,
            "notification_type": notification_type,
            "user_id": user.id,
            "biz_type": biz_type,
            "biz_id": biz_id,
        },
    )
    return notification


def resolve_notification_route_path(notification: SystemNotification) -> str:
    if notification.biz_type == "borrow_application" and notification.biz_id:
        return f"/borrowing/applications?applicationId={notification.biz_id}"

    if notification.biz_type == "destroy_application" and notification.biz_id:
        return f"/destruction/applications?applicationId={notification.biz_id}"

    if notification.biz_type == "scan_task" and notification.biz_id:
        return f"/digitization/scan-tasks/{notification.biz_id}"

    if notification.biz_type == "scan_task_item" and notification.biz_id:
        task_item = ScanTaskItem.objects.filter(id=notification.biz_id).values("task_id").first()
        if task_item and task_item["task_id"]:
            return f"/digitization/scan-tasks/{task_item['task_id']}?itemId={notification.biz_id}"
        return "/digitization/scan-tasks"

    if notification.biz_type == "archive_record" and notification.biz_id:
        return f"/archives/records?archiveId={notification.biz_id}"

    if notification.biz_type == "archive_file" and notification.biz_id:
        archive_file = ArchiveFile.objects.filter(id=notification.biz_id).values("archive_id").first()
        if archive_file and archive_file["archive_id"]:
            return f"/archives/records?archiveId={archive_file['archive_id']}&fileId={notification.biz_id}"
        return "/archives/records"

    if notification.biz_type == "report_export":
        return "/reports/center"

    if notification.biz_type == "system_user":
        if notification.biz_id:
            return f"/system/management?tab=users&userId={notification.biz_id}"
        return "/system/management"

    return f"/notifications/messages?notificationId={notification.id}"


def build_notification_page_position(*, queryset, notification: SystemNotification, page_size: int) -> dict[str, int]:
    before_count = queryset.exclude(id=notification.id).filter(
        Q(is_read__lt=notification.is_read)
        | Q(is_read=notification.is_read, created_at__gt=notification.created_at)
        | Q(is_read=notification.is_read, created_at=notification.created_at, id__gt=notification.id)
    ).count()
    return {
        "page": before_count // page_size + 1,
        "page_size": page_size,
        "row_index": before_count,
    }


@transaction.atomic
def create_email_task(
    *,
    receiver_user,
    receiver_email: str,
    subject: str,
    content: str,
    biz_type: str | None = None,
    biz_id: int | None = None,
) -> EmailTask:
    email_task = EmailTask.objects.create(
        receiver_user=receiver_user,
        receiver_email=receiver_email,
        subject=subject,
        content=content,
        biz_type=biz_type,
        biz_id=biz_id,
    )
    logger.info(
        "创建邮件任务",
        extra={
            "email_task_id": email_task.id,
            "receiver_email": mask_email_address(receiver_email),
            "biz_type": biz_type,
            "biz_id": biz_id,
        },
    )
    return email_task


def process_email_task(email_task_id: int) -> None:
    email_task = EmailTask.objects.filter(id=email_task_id).first()
    if not email_task:
        return

    email_task.send_status = EmailTaskStatus.RUNNING
    email_task.error_message = None
    email_task.save(update_fields=["send_status", "error_message", "updated_at"])

    try:
        send_result = send_mail(
            subject=email_task.subject,
            message=email_task.content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email_task.receiver_email],
            fail_silently=False,
        )
        if send_result <= 0:
            raise RuntimeError("邮件发送结果为空。")

        email_task.send_status = EmailTaskStatus.SUCCESS
        email_task.sent_at = timezone.now()
        email_task.save(update_fields=["send_status", "sent_at", "updated_at"])
        logger.info(
            "邮件发送成功",
            extra={
                "email_task_id": email_task.id,
                "receiver_email": mask_email_address(email_task.receiver_email),
            },
        )
    except Exception as exc:
        email_task.send_status = EmailTaskStatus.FAILED
        email_task.retry_count += 1
        email_task.error_message = str(exc)
        email_task.save(update_fields=["send_status", "retry_count", "error_message", "updated_at"])
        logger.exception(
            "邮件发送失败",
            extra={
                "email_task_id": email_task.id,
                "receiver_email": mask_email_address(email_task.receiver_email),
            },
        )


def dispatch_email_task(email_task: EmailTask) -> None:
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        process_email_task(email_task.id)
        return

    try:
        from apps.notifications.tasks import send_email_task

        send_email_task.delay(email_task.id)
    except Exception:
        logger.warning("Celery 邮件发送不可用，回退为同步发送", extra={"email_task_id": email_task.id})
        process_email_task(email_task.id)


def get_email_channel_diagnostics() -> dict[str, object]:
    backend_path = getattr(settings, "EMAIL_BACKEND", "").strip()
    issues: list[str] = []

    if not backend_path:
        issues.append("未配置 EMAIL_BACKEND。")
    elif backend_path in LOCAL_ONLY_EMAIL_BACKENDS:
        issues.append("当前邮件后端仅用于本地调试，不会将邮件发送到外部邮箱。")

    if backend_path == "django.core.mail.backends.smtp.EmailBackend":
        if not getattr(settings, "EMAIL_HOST", "").strip():
            issues.append("未配置 EMAIL_HOST。")
        if not getattr(settings, "DEFAULT_FROM_EMAIL", "").strip():
            issues.append("未配置 DEFAULT_FROM_EMAIL。")
        if getattr(settings, "EMAIL_USE_TLS", False) and getattr(settings, "EMAIL_USE_SSL", False):
            issues.append("EMAIL_USE_TLS 与 EMAIL_USE_SSL 不能同时启用。")

    return {
        "backend": backend_path,
        "is_external_ready": not issues,
        "issues": issues,
    }


def send_verification_email(*, receiver_email: str, subject: str, content: str) -> EmailTask:
    diagnostics = get_email_channel_diagnostics()
    if not diagnostics["is_external_ready"]:
        raise ValueError("；".join(diagnostics["issues"]))

    email_task = create_email_task(
        receiver_user=None,
        receiver_email=receiver_email,
        subject=subject,
        content=content,
        biz_type="notification_channel_verification",
    )
    process_email_task(email_task.id)
    email_task.refresh_from_db()

    if email_task.send_status != EmailTaskStatus.SUCCESS:
        raise RuntimeError(email_task.error_message or "邮件验证发送失败。")

    return email_task


def send_verification_webhook(
    *,
    webhook_url: str,
    subject: str,
    content: str,
    timeout: int = 5,
    headers: dict[str, str] | None = None,
) -> dict[str, object]:
    payload = {
        "title": subject,
        "message": content,
        "event": "notification_channel_verification",
        "sent_at": timezone.now().isoformat(),
    }
    request_headers = {
        "Content-Type": "application/json",
        "User-Agent": "ASDSystem-Notification-Verification/1.0",
    }
    if headers:
        request_headers.update(headers)

    request = Request(
        webhook_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = response.getcode() or 200
            response_text = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        logger.exception(
            "Webhook 验证发送失败",
            extra={"webhook_url": mask_webhook_url(webhook_url), "status_code": exc.code},
        )
        raise RuntimeError(f"Webhook 返回异常状态 {exc.code}：{response_text or exc.reason}") from exc
    except URLError as exc:
        logger.exception("Webhook 验证发送失败", extra={"webhook_url": mask_webhook_url(webhook_url)})
        raise RuntimeError(f"Webhook 请求失败：{exc.reason}") from exc

    logger.info("Webhook 验证发送成功", extra={"webhook_url": mask_webhook_url(webhook_url), "status_code": status_code})
    return {
        "status_code": status_code,
        "response_text": response_text,
    }


@transaction.atomic
def mark_notification_as_read(*, notification: SystemNotification) -> SystemNotification:
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at", "updated_at"])
    return notification


@transaction.atomic
def mark_notifications_as_read(*, user) -> int:
    current_time = timezone.now()
    updated_count = (
        SystemNotification.objects.filter(user=user, is_read=False)
        .update(is_read=True, read_at=current_time, updated_at=current_time)
    )
    return updated_count


def build_notification_summary(user) -> dict[str, int]:
    total_count = SystemNotification.objects.filter(user=user).count()
    unread_count = SystemNotification.objects.filter(user=user, is_read=False).count()
    reminder_unread_count = SystemNotification.objects.filter(
        user=user,
        is_read=False,
        notification_type=NotificationType.BORROW_REMINDER,
    ).count()
    return {
        "total_count": total_count,
        "unread_count": unread_count,
        "reminder_unread_count": reminder_unread_count,
    }
