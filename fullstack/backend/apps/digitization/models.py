from django.db import models

from apps.common.models import OperatorStampedModel, TimeStampedModel


class ScanTaskStatus(models.TextChoices):
    PENDING = "PENDING", "待开始"
    IN_PROGRESS = "IN_PROGRESS", "进行中"
    COMPLETED = "COMPLETED", "已完成"
    FAILED = "FAILED", "已失败"


class ScanTaskItemStatus(models.TextChoices):
    PENDING = "PENDING", "待上传"
    PROCESSING = "PROCESSING", "处理中"
    COMPLETED = "COMPLETED", "已完成"
    FAILED = "FAILED", "已失败"


class FileProcessJobType(models.TextChoices):
    THUMBNAIL = "THUMBNAIL", "缩略图生成"
    TEXT_EXTRACT = "TEXT_EXTRACT", "文本提取"


class FileProcessJobStatus(models.TextChoices):
    PENDING = "PENDING", "待处理"
    PROCESSING = "PROCESSING", "处理中"
    SUCCESS = "SUCCESS", "成功"
    FAILED = "FAILED", "失败"


class ScanTask(OperatorStampedModel):
    task_no = models.CharField(max_length=64, unique=True, verbose_name="任务编号")
    task_name = models.CharField(max_length=200, verbose_name="任务名称")
    assigned_user_id = models.PositiveBigIntegerField(db_index=True, verbose_name="指派执行人")
    assigned_by = models.PositiveBigIntegerField(db_index=True, verbose_name="指派人")
    status = models.CharField(
        max_length=16,
        choices=ScanTaskStatus.choices,
        default=ScanTaskStatus.PENDING,
        db_index=True,
        verbose_name="任务状态",
    )
    total_count = models.PositiveIntegerField(default=0, verbose_name="档案总数")
    completed_count = models.PositiveIntegerField(default=0, verbose_name="完成数")
    failed_count = models.PositiveIntegerField(default=0, verbose_name="失败数")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")
    remark = models.CharField(max_length=255, null=True, blank=True, verbose_name="备注")

    class Meta:
        db_table = "scan_task"
        ordering = ["-id"]
        verbose_name = "扫描任务"
        verbose_name_plural = "扫描任务"


class ScanTaskItem(TimeStampedModel):
    task = models.ForeignKey(
        ScanTask,
        on_delete=models.CASCADE,
        related_name="items",
        db_column="task_id",
        verbose_name="扫描任务",
    )
    archive = models.ForeignKey(
        "archives.ArchiveRecord",
        on_delete=models.PROTECT,
        related_name="scan_task_items",
        db_column="archive_id",
        verbose_name="档案",
    )
    assignee_user_id = models.PositiveBigIntegerField(db_index=True, verbose_name="执行人")
    status = models.CharField(
        max_length=16,
        choices=ScanTaskItemStatus.choices,
        default=ScanTaskItemStatus.PENDING,
        db_index=True,
        verbose_name="明细状态",
    )
    uploaded_file_count = models.PositiveIntegerField(default=0, verbose_name="已上传文件数")
    last_uploaded_at = models.DateTimeField(null=True, blank=True, verbose_name="最后上传时间")
    error_message = models.CharField(max_length=500, null=True, blank=True, verbose_name="异常说明")

    class Meta:
        db_table = "scan_task_item"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["task", "archive"], name="uniq_scan_task_archive")
        ]
        verbose_name = "扫描任务明细"
        verbose_name_plural = "扫描任务明细"


class FileProcessJob(models.Model):
    archive_file = models.ForeignKey(
        "archives.ArchiveFile",
        on_delete=models.CASCADE,
        related_name="process_jobs",
        db_column="archive_file_id",
        verbose_name="档案文件",
    )
    job_type = models.CharField(max_length=32, choices=FileProcessJobType.choices, db_index=True)
    status = models.CharField(
        max_length=16,
        choices=FileProcessJobStatus.choices,
        default=FileProcessJobStatus.PENDING,
        db_index=True,
        verbose_name="处理状态",
    )
    retry_count = models.PositiveIntegerField(default=0, verbose_name="重试次数")
    error_message = models.CharField(max_length=500, null=True, blank=True, verbose_name="错误信息")
    started_at = models.DateTimeField(null=True, blank=True, verbose_name="开始时间")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="结束时间")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "file_process_job"
        ordering = ["id"]
        verbose_name = "文件处理任务"
        verbose_name_plural = "文件处理任务"
