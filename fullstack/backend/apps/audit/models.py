import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class AuditResultStatus(models.TextChoices):
    SUCCESS = "SUCCESS", "成功"
    FAILED = "FAILED", "失败"
    DENIED = "DENIED", "拒绝"


class ArchiveFileAccessAction(models.TextChoices):
    PREVIEW = "PREVIEW", "预览"
    DOWNLOAD = "DOWNLOAD", "下载"


class AuditLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        db_column="user_id",
        verbose_name="操作用户",
    )
    username = models.CharField(max_length=64, blank=True, default="", db_index=True, verbose_name="用户名快照")
    real_name = models.CharField(max_length=100, blank=True, default="", verbose_name="姓名快照")
    module_name = models.CharField(max_length=64, db_index=True, verbose_name="模块名称")
    action_code = models.CharField(max_length=64, db_index=True, verbose_name="动作编码")
    biz_type = models.CharField(max_length=64, null=True, blank=True, db_index=True, verbose_name="业务类型")
    biz_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True, verbose_name="业务标识")
    target_repr = models.CharField(max_length=255, null=True, blank=True, verbose_name="目标摘要")
    result_status = models.CharField(
        max_length=16,
        choices=AuditResultStatus.choices,
        default=AuditResultStatus.SUCCESS,
        db_index=True,
        verbose_name="结果状态",
    )
    description = models.TextField(verbose_name="操作描述")
    ip_address = models.CharField(max_length=64, null=True, blank=True, verbose_name="客户端 IP")
    user_agent = models.CharField(max_length=255, null=True, blank=True, verbose_name="客户端 UA")
    request_method = models.CharField(max_length=16, null=True, blank=True, verbose_name="请求方法")
    request_path = models.CharField(max_length=255, null=True, blank=True, verbose_name="请求路径")
    extra_data_json = models.JSONField(default=dict, blank=True, verbose_name="补充数据")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="创建时间")

    class Meta:
        db_table = "sys_audit_log"
        ordering = ["-id"]
        verbose_name = "审计日志"
        verbose_name_plural = "审计日志"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("审计日志不允许修改。")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.module_name}:{self.action_code}:{self.username}"


class ArchiveFileAccessTicket(models.Model):
    archive_file = models.ForeignKey(
        "archives.ArchiveFile",
        on_delete=models.CASCADE,
        related_name="access_tickets",
        db_column="archive_file_id",
        verbose_name="档案文件",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="archive_file_access_tickets",
        db_column="user_id",
        verbose_name="申请用户",
    )
    username = models.CharField(max_length=64, blank=True, default="", db_index=True, verbose_name="用户名快照")
    real_name = models.CharField(max_length=100, blank=True, default="", verbose_name="姓名快照")
    access_action = models.CharField(
        max_length=16,
        choices=ArchiveFileAccessAction.choices,
        db_index=True,
        verbose_name="访问动作",
    )
    token = models.CharField(max_length=64, unique=True, default="", db_index=True, verbose_name="访问票据")
    purpose = models.CharField(max_length=255, null=True, blank=True, verbose_name="下载用途")
    watermark_text = models.CharField(max_length=255, null=True, blank=True, verbose_name="水印文本")
    expires_at = models.DateTimeField(db_index=True, verbose_name="失效时间")
    access_count = models.PositiveIntegerField(default=0, verbose_name="访问次数")
    last_accessed_at = models.DateTimeField(null=True, blank=True, verbose_name="最后访问时间")
    used_at = models.DateTimeField(null=True, blank=True, verbose_name="下载使用时间")
    is_active = models.BooleanField(default=True, db_index=True, verbose_name="是否有效")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "archive_file_access_ticket"
        ordering = ["-id"]
        verbose_name = "档案文件访问票据"
        verbose_name_plural = "档案文件访问票据"

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = uuid.uuid4().hex
        super().save(*args, **kwargs)

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

