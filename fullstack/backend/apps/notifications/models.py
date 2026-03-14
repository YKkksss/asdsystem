from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel


class NotificationType(models.TextChoices):
    BORROW_APPROVAL = "BORROW_APPROVAL", "借阅审批通知"
    BORROW_REMINDER = "BORROW_REMINDER", "催还通知"
    RETURN_CONFIRM = "RETURN_CONFIRM", "归还确认通知"
    DESTROY_APPROVAL = "DESTROY_APPROVAL", "销毁审批通知"
    SYSTEM = "SYSTEM", "系统通知"


class EmailTaskStatus(models.TextChoices):
    PENDING = "PENDING", "待发送"
    RUNNING = "RUNNING", "发送中"
    SUCCESS = "SUCCESS", "发送成功"
    FAILED = "FAILED", "发送失败"


class SystemNotification(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="system_notifications",
        db_column="user_id",
        verbose_name="接收用户",
    )
    notification_type = models.CharField(
        max_length=32,
        choices=NotificationType.choices,
        db_index=True,
        verbose_name="通知类型",
    )
    title = models.CharField(max_length=255, verbose_name="标题")
    content = models.TextField(verbose_name="通知内容")
    biz_type = models.CharField(max_length=64, null=True, blank=True, db_index=True, verbose_name="业务类型")
    biz_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True, verbose_name="业务标识")
    is_read = models.BooleanField(default=False, db_index=True, verbose_name="是否已读")
    read_at = models.DateTimeField(null=True, blank=True, verbose_name="已读时间")

    class Meta:
        db_table = "sys_notification"
        ordering = ["is_read", "-created_at", "-id"]
        verbose_name = "站内通知"
        verbose_name_plural = "站内通知"

    def __str__(self) -> str:
        return self.title


class EmailTask(TimeStampedModel):
    receiver_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_tasks",
        db_column="receiver_user_id",
        verbose_name="接收用户",
    )
    receiver_email = models.EmailField(max_length=128, db_index=True, verbose_name="接收邮箱")
    subject = models.CharField(max_length=255, verbose_name="邮件主题")
    content = models.TextField(verbose_name="邮件内容")
    biz_type = models.CharField(max_length=64, null=True, blank=True, db_index=True, verbose_name="业务类型")
    biz_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True, verbose_name="业务标识")
    send_status = models.CharField(
        max_length=16,
        choices=EmailTaskStatus.choices,
        default=EmailTaskStatus.PENDING,
        db_index=True,
        verbose_name="发送状态",
    )
    scheduled_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name="计划发送时间")
    sent_at = models.DateTimeField(null=True, blank=True, db_index=True, verbose_name="发送时间")
    retry_count = models.PositiveIntegerField(default=0, verbose_name="重试次数")
    error_message = models.CharField(max_length=255, null=True, blank=True, verbose_name="失败原因")

    class Meta:
        db_table = "sys_email_task"
        ordering = ["send_status", "-scheduled_at", "-id"]
        verbose_name = "邮件任务"
        verbose_name_plural = "邮件任务"

    def __str__(self) -> str:
        return f"{self.receiver_email} {self.subject}"

