from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.archives.models import ArchiveRecord, ArchiveStorageLocation
from apps.common.models import OperatorStampedModel, TimeStampedModel
from apps.organizations.models import Department


class BorrowApplicationStatus(models.TextChoices):
    DRAFT = "DRAFT", "草稿"
    PENDING_APPROVAL = "PENDING_APPROVAL", "待审批"
    APPROVED = "APPROVED", "已通过"
    REJECTED = "REJECTED", "已驳回"
    WITHDRAWN = "WITHDRAWN", "已撤回"
    CHECKED_OUT = "CHECKED_OUT", "借出中"
    OVERDUE = "OVERDUE", "已超期"
    RETURNED = "RETURNED", "已归还"


class BorrowApprovalAction(models.TextChoices):
    APPROVE = "APPROVE", "通过"
    REJECT = "REJECT", "驳回"


class BorrowReturnStatus(models.TextChoices):
    SUBMITTED = "SUBMITTED", "已提交归还"
    CONFIRMED = "CONFIRMED", "已确认入库"
    REJECTED = "REJECTED", "归还验收不通过"


class BorrowHandoverType(models.TextChoices):
    PHOTO = "PHOTO", "照片"
    DOCUMENT = "DOCUMENT", "交接单"
    BOTH = "BOTH", "照片和交接单"


class BorrowReturnAttachmentType(models.TextChoices):
    PHOTO = "PHOTO", "照片"
    HANDOVER_DOC = "HANDOVER_DOC", "交接单"


class BorrowReminderType(models.TextChoices):
    BEFORE_DUE = "BEFORE_DUE", "到期前提醒"
    DUE_TODAY = "DUE_TODAY", "到期当天提醒"
    OVERDUE = "OVERDUE", "超期提醒"


class BorrowReminderChannel(models.TextChoices):
    SITE = "SITE", "站内通知"
    EMAIL = "EMAIL", "邮件"


class BorrowReminderSendStatus(models.TextChoices):
    SUCCESS = "SUCCESS", "成功"
    FAILED = "FAILED", "失败"


class BorrowApplication(OperatorStampedModel):
    application_no = models.CharField(max_length=64, unique=True, verbose_name="申请编号")
    archive = models.ForeignKey(
        ArchiveRecord,
        on_delete=models.PROTECT,
        related_name="borrow_applications",
        db_column="archive_id",
        verbose_name="档案",
    )
    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="borrow_applications",
        db_column="applicant_id",
        verbose_name="申请人",
    )
    applicant_dept = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="borrow_applications",
        db_column="applicant_dept_id",
        verbose_name="申请部门",
    )
    purpose = models.CharField(max_length=500, verbose_name="借阅用途")
    expected_return_at = models.DateTimeField(db_index=True, verbose_name="预计归还时间")
    status = models.CharField(
        max_length=32,
        choices=BorrowApplicationStatus.choices,
        default=BorrowApplicationStatus.DRAFT,
        db_index=True,
        verbose_name="借阅状态",
    )
    current_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="current_borrow_approvals",
        db_column="current_approver_id",
        verbose_name="当前审批人",
    )
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name="提交时间")
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name="审批通过时间")
    rejected_at = models.DateTimeField(null=True, blank=True, verbose_name="驳回时间")
    withdrawn_at = models.DateTimeField(null=True, blank=True, verbose_name="撤回时间")
    checkout_at = models.DateTimeField(null=True, blank=True, verbose_name="实际借出时间")
    returned_at = models.DateTimeField(null=True, blank=True, verbose_name="实际归还时间")
    reject_reason = models.CharField(max_length=255, null=True, blank=True, verbose_name="驳回原因")
    is_overdue = models.BooleanField(default=False, db_index=True, verbose_name="是否超期")
    overdue_days = models.PositiveIntegerField(default=0, verbose_name="超期天数")

    class Meta:
        db_table = "borrow_application"
        ordering = ["-id"]
        verbose_name = "借阅申请"
        verbose_name_plural = "借阅申请"

    def __str__(self) -> str:
        return self.application_no


class BorrowApprovalRecord(TimeStampedModel):
    application = models.ForeignKey(
        BorrowApplication,
        on_delete=models.CASCADE,
        related_name="approval_records",
        db_column="application_id",
        verbose_name="借阅申请",
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="borrow_approval_records",
        db_column="approver_id",
        verbose_name="审批人",
    )
    action = models.CharField(max_length=16, choices=BorrowApprovalAction.choices, db_index=True, verbose_name="审批动作")
    opinion = models.CharField(max_length=500, null=True, blank=True, verbose_name="审批意见")
    approved_at = models.DateTimeField(default=timezone.now, verbose_name="审批时间")

    class Meta:
        db_table = "borrow_approval_record"
        ordering = ["-id"]
        verbose_name = "借阅审批记录"
        verbose_name_plural = "借阅审批记录"


class BorrowCheckoutRecord(TimeStampedModel):
    application = models.OneToOneField(
        BorrowApplication,
        on_delete=models.CASCADE,
        related_name="checkout_record",
        db_column="application_id",
        verbose_name="借阅申请",
    )
    archive = models.ForeignKey(
        ArchiveRecord,
        on_delete=models.PROTECT,
        related_name="borrow_checkout_records",
        db_column="archive_id",
        verbose_name="档案",
    )
    borrower = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="borrow_checkout_received_records",
        db_column="borrower_id",
        verbose_name="领取人",
    )
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="borrow_checkout_operated_records",
        db_column="operator_id",
        verbose_name="办理档案员",
    )
    checkout_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name="出库时间")
    expected_return_at = models.DateTimeField(db_index=True, verbose_name="预计归还时间")
    location_snapshot = models.CharField(max_length=255, null=True, blank=True, verbose_name="借出前位置快照")
    checkout_note = models.CharField(max_length=255, null=True, blank=True, verbose_name="出库备注")

    class Meta:
        db_table = "borrow_checkout_record"
        ordering = ["-id"]
        verbose_name = "出库登记"
        verbose_name_plural = "出库登记"


class BorrowReturnRecord(TimeStampedModel):
    application = models.OneToOneField(
        BorrowApplication,
        on_delete=models.CASCADE,
        related_name="return_record",
        db_column="application_id",
        verbose_name="借阅申请",
    )
    archive = models.ForeignKey(
        ArchiveRecord,
        on_delete=models.PROTECT,
        related_name="borrow_return_records",
        db_column="archive_id",
        verbose_name="档案",
    )
    returned_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="borrow_return_submitted_records",
        db_column="returned_by_user_id",
        verbose_name="归还提交人",
    )
    received_by_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="borrow_return_received_records",
        db_column="received_by_user_id",
        verbose_name="验收档案员",
    )
    return_status = models.CharField(
        max_length=16,
        choices=BorrowReturnStatus.choices,
        default=BorrowReturnStatus.SUBMITTED,
        db_index=True,
        verbose_name="归还确认状态",
    )
    handover_type = models.CharField(max_length=16, choices=BorrowHandoverType.choices, verbose_name="交接类型")
    handover_note = models.CharField(max_length=255, null=True, blank=True, verbose_name="交接说明")
    returned_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name="归还提交时间")
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="确认入库时间")
    location_after_return = models.ForeignKey(
        ArchiveStorageLocation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="borrow_return_records",
        db_column="location_after_return_id",
        verbose_name="归还后位置",
    )
    confirm_note = models.CharField(max_length=255, null=True, blank=True, verbose_name="验收备注")

    class Meta:
        db_table = "borrow_return_record"
        ordering = ["-id"]
        verbose_name = "归还记录"
        verbose_name_plural = "归还记录"


class BorrowReturnAttachment(TimeStampedModel):
    return_record = models.ForeignKey(
        BorrowReturnRecord,
        on_delete=models.CASCADE,
        related_name="attachments",
        db_column="return_record_id",
        verbose_name="归还记录",
    )
    attachment_type = models.CharField(
        max_length=16,
        choices=BorrowReturnAttachmentType.choices,
        db_index=True,
        verbose_name="附件类型",
    )
    file_name = models.CharField(max_length=255, verbose_name="文件名称")
    file_path = models.CharField(max_length=500, verbose_name="文件路径")
    file_size = models.PositiveBigIntegerField(default=0, verbose_name="文件大小")
    uploaded_by = models.PositiveBigIntegerField(db_index=True, verbose_name="上传人")

    class Meta:
        db_table = "borrow_return_attachment"
        ordering = ["id"]
        verbose_name = "归还附件"
        verbose_name_plural = "归还附件"


class BorrowReminderRecord(TimeStampedModel):
    application = models.ForeignKey(
        BorrowApplication,
        on_delete=models.CASCADE,
        related_name="reminder_records",
        db_column="application_id",
        verbose_name="借阅申请",
    )
    reminder_type = models.CharField(
        max_length=16,
        choices=BorrowReminderType.choices,
        db_index=True,
        verbose_name="提醒类型",
    )
    channel = models.CharField(
        max_length=16,
        choices=BorrowReminderChannel.choices,
        db_index=True,
        verbose_name="发送渠道",
    )
    receiver_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="borrow_reminder_records",
        db_column="receiver_user_id",
        verbose_name="接收用户",
    )
    receiver_email = models.EmailField(max_length=128, null=True, blank=True, verbose_name="接收邮箱")
    send_status = models.CharField(
        max_length=16,
        choices=BorrowReminderSendStatus.choices,
        default=BorrowReminderSendStatus.SUCCESS,
        db_index=True,
        verbose_name="发送状态",
    )
    sent_at = models.DateTimeField(default=timezone.now, db_index=True, verbose_name="发送时间")
    content_summary = models.CharField(max_length=255, null=True, blank=True, verbose_name="内容摘要")
    notification = models.ForeignKey(
        "notifications.SystemNotification",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="borrow_reminder_records",
        db_column="notification_id",
        verbose_name="站内通知",
    )
    email_task = models.ForeignKey(
        "notifications.EmailTask",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="borrow_reminder_records",
        db_column="email_task_id",
        verbose_name="邮件任务",
    )

    class Meta:
        db_table = "borrow_reminder_record"
        ordering = ["-sent_at", "-id"]
        verbose_name = "催还记录"
        verbose_name_plural = "催还记录"
