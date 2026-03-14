import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.notifications.models import EmailTask, EmailTaskStatus, NotificationType, SystemNotification


logger = logging.getLogger(__name__)


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
            "receiver_email": receiver_email,
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
        logger.info("邮件发送成功", extra={"email_task_id": email_task.id})
    except Exception as exc:
        email_task.send_status = EmailTaskStatus.FAILED
        email_task.retry_count += 1
        email_task.error_message = str(exc)
        email_task.save(update_fields=["send_status", "retry_count", "error_message", "updated_at"])
        logger.exception("邮件发送失败", extra={"email_task_id": email_task.id})


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
