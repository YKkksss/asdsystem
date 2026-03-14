from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.archives.models import ArchiveRecord
from apps.common.models import OperatorStampedModel, TimeStampedModel
from apps.organizations.models import Department


class DestroyApplicationStatus(models.TextChoices):
    PENDING_APPROVAL = "PENDING_APPROVAL", "待审批"
    APPROVED = "APPROVED", "已通过"
    REJECTED = "REJECTED", "已驳回"
    EXECUTED = "EXECUTED", "已执行销毁"


class DestroyApprovalAction(models.TextChoices):
    APPROVE = "APPROVE", "通过"
    REJECT = "REJECT", "驳回"


class DestroyApplication(OperatorStampedModel):
    application_no = models.CharField(max_length=64, unique=True, verbose_name="申请编号")
    archive = models.ForeignKey(
        ArchiveRecord,
        on_delete=models.PROTECT,
        related_name="destroy_applications",
        db_column="archive_id",
        verbose_name="档案",
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="destroy_applications",
        db_column="applicant_id",
        verbose_name="申请人",
    )
    applicant_dept = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="destroy_applications",
        db_column="applicant_dept_id",
        verbose_name="申请部门",
    )
    reason = models.CharField(max_length=500, verbose_name="销毁原因")
    basis = models.CharField(max_length=500, verbose_name="销毁依据")
    status = models.CharField(
        max_length=32,
        choices=DestroyApplicationStatus.choices,
        default=DestroyApplicationStatus.PENDING_APPROVAL,
        db_index=True,
        verbose_name="销毁状态",
    )
    current_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="current_destroy_approvals",
        db_column="current_approver_id",
        verbose_name="当前审批人",
    )
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name="提交时间")
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="审批通过时间")
    rejected_at = models.DateTimeField(null=True, blank=True, verbose_name="驳回时间")
    executed_at = models.DateTimeField(null=True, blank=True, verbose_name="执行时间")
    reject_reason = models.CharField(max_length=255, null=True, blank=True, verbose_name="驳回原因")

    class Meta:
        db_table = "destroy_application"
        ordering = ["-id"]
        verbose_name = "销毁申请"
        verbose_name_plural = "销毁申请"

    def __str__(self) -> str:
        return self.application_no


class DestroyApprovalRecord(TimeStampedModel):
    application = models.ForeignKey(
        DestroyApplication,
        on_delete=models.CASCADE,
        related_name="approval_records",
        db_column="application_id",
        verbose_name="销毁申请",
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="destroy_approval_records",
        db_column="approver_id",
        verbose_name="审批人",
    )
    action = models.CharField(max_length=16, choices=DestroyApprovalAction.choices, db_index=True, verbose_name="审批动作")
    opinion = models.CharField(max_length=500, null=True, blank=True, verbose_name="审批意见")
    approved_at = models.DateTimeField(default=timezone.now, verbose_name="审批时间")

    class Meta:
        db_table = "destroy_approval_record"
        ordering = ["-id"]
        verbose_name = "销毁审批记录"
        verbose_name_plural = "销毁审批记录"


class DestroyExecutionRecord(TimeStampedModel):
    application = models.OneToOneField(
        DestroyApplication,
        on_delete=models.CASCADE,
        related_name="execution_record",
        db_column="application_id",
        verbose_name="销毁申请",
    )
    archive = models.ForeignKey(
        ArchiveRecord,
        on_delete=models.PROTECT,
        related_name="destroy_execution_records",
        db_column="archive_id",
        verbose_name="档案",
    )
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="destroy_execution_records",
        db_column="operator_id",
        verbose_name="执行人",
    )
    executed_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name="执行时间")
    execution_note = models.CharField(max_length=500, verbose_name="执行说明")
    location_snapshot = models.CharField(max_length=255, null=True, blank=True, verbose_name="销毁前位置快照")
    archive_snapshot_json = models.JSONField(default=dict, verbose_name="销毁时档案快照")

    class Meta:
        db_table = "destroy_execution_record"
        ordering = ["-id"]
        verbose_name = "销毁执行记录"
        verbose_name_plural = "销毁执行记录"


class DestroyExecutionAttachment(TimeStampedModel):
    execution_record = models.ForeignKey(
        DestroyExecutionRecord,
        on_delete=models.CASCADE,
        related_name="attachments",
        db_column="execution_record_id",
        verbose_name="销毁执行记录",
    )
    file_name = models.CharField(max_length=255, verbose_name="文件名称")
    file_path = models.CharField(max_length=500, verbose_name="文件路径")
    file_size = models.PositiveBigIntegerField(default=0, verbose_name="文件大小")
    uploaded_by = models.PositiveBigIntegerField(db_index=True, verbose_name="上传人")

    class Meta:
        db_table = "destroy_execution_attachment"
        ordering = ["id"]
        verbose_name = "销毁执行附件"
        verbose_name_plural = "销毁执行附件"

