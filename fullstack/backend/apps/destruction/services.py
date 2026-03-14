import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import record_audit_log
from apps.archives.models import ArchiveRecord, ArchiveStatus
from apps.archives.services import build_archive_snapshot, transition_archive_status
from apps.borrowing.models import BorrowApplication, BorrowApplicationStatus
from apps.destruction.models import (
    DestroyApplication,
    DestroyApplicationStatus,
    DestroyApprovalAction,
    DestroyApprovalRecord,
    DestroyExecutionAttachment,
    DestroyExecutionRecord,
)
from apps.notifications.models import NotificationType
from apps.notifications.services import create_system_notification


logger = logging.getLogger(__name__)
User = get_user_model()

ACTIVE_DESTROY_APPLICATION_STATUSES = {
    DestroyApplicationStatus.PENDING_APPROVAL,
    DestroyApplicationStatus.APPROVED,
}
ACTIVE_BORROW_APPLICATION_STATUSES = {
    BorrowApplicationStatus.PENDING_APPROVAL,
    BorrowApplicationStatus.APPROVED,
    BorrowApplicationStatus.CHECKED_OUT,
    BorrowApplicationStatus.OVERDUE,
}
ALLOWED_DESTROY_ATTACHMENT_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
BIZ_TYPE_DESTROY_APPLICATION = "destroy_application"


def _has_any_role(user, role_codes: set[str]) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if not hasattr(user, "roles"):
        return False
    return user.roles.filter(role_code__in=role_codes, status=True).exists()


def is_archive_manager_user(user) -> bool:
    return _has_any_role(user, {"ADMIN", "ARCHIVIST"})


def is_system_admin_user(user) -> bool:
    return _has_any_role(user, {"ADMIN"})


def is_admin_or_auditor_user(user) -> bool:
    return _has_any_role(user, {"ADMIN", "AUDITOR"})


def can_user_approve_destroy_application(user, application: DestroyApplication) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if not is_system_admin_user(user):
        return False
    if application.current_approver_id is None:
        return True
    return application.current_approver_id == user.id


def can_user_execute_destroy_application(user, application: DestroyApplication) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if application.status != DestroyApplicationStatus.APPROVED:
        return False
    return is_archive_manager_user(user)


def build_destroy_application_no() -> str:
    return f"DST{timezone.now():%Y%m%d%H%M%S}{uuid.uuid4().hex[:6].upper()}"


def resolve_destroy_approver() -> User:
    approver = (
        User.objects.filter(status=True, roles__role_code="ADMIN", roles__status=True)
        .distinct()
        .order_by("id")
        .first()
    )
    if approver:
        return approver
    raise ValidationError("系统中不存在可用的管理员审批人，暂时无法发起销毁申请。")


def build_destroy_archive_display(application: DestroyApplication) -> str:
    return f"{application.archive.archive_code}《{application.archive.title}》"


def notify_destroy_application_submitted(application: DestroyApplication, approver) -> None:
    create_system_notification(
        user=approver,
        notification_type=NotificationType.DESTROY_APPROVAL,
        title="档案销毁待审批",
        content=(
            f"{application.applicant.real_name} 提交了档案 {build_destroy_archive_display(application)} 的销毁申请，"
            f"请核对销毁原因与依据后完成审批。"
        ),
        biz_type=BIZ_TYPE_DESTROY_APPLICATION,
        biz_id=application.id,
    )


def notify_destroy_application_result(application: DestroyApplication, approved: bool, opinion: str | None = None) -> None:
    title = "档案销毁审批已通过" if approved else "档案销毁审批已驳回"
    result_text = "审批通过，可进入销毁执行环节。" if approved else f"审批已驳回，原因：{opinion or application.reject_reason or '无'}。"
    create_system_notification(
        user=application.applicant,
        notification_type=NotificationType.DESTROY_APPROVAL,
        title=title,
        content=f"档案 {build_destroy_archive_display(application)} 的销毁申请处理完成，{result_text}",
        biz_type=BIZ_TYPE_DESTROY_APPLICATION,
        biz_id=application.id,
    )


def notify_destroy_application_executed(application: DestroyApplication, operator) -> None:
    recipients: dict[int, object] = {application.applicant_id: application.applicant}
    latest_approval = application.approval_records.select_related("approver").order_by("-id").first()
    approver = latest_approval.approver if latest_approval else None
    if approver:
        recipients[approver.id] = approver
    for user in recipients.values():
        create_system_notification(
            user=user,
            notification_type=NotificationType.DESTROY_APPROVAL,
            title="档案销毁已执行",
            content=(
                f"档案 {build_destroy_archive_display(application)} 已由 {operator.real_name} 完成销毁执行，"
                "系统已保留执行记录与附件。"
            ),
            biz_type=BIZ_TYPE_DESTROY_APPLICATION,
            biz_id=application.id,
        )


def validate_destroy_attachment(uploaded_file) -> None:
    extension = Path(uploaded_file.name).suffix.lower().lstrip(".")
    if extension not in ALLOWED_DESTROY_ATTACHMENT_EXTENSIONS:
        raise ValidationError(f"不支持的销毁附件格式：{extension or '未知'}。")

    max_size = settings.ARCHIVE_UPLOAD_MAX_SIZE_MB * 1024 * 1024
    if uploaded_file.size > max_size:
        raise ValidationError(f"单个销毁附件大小不能超过 {settings.ARCHIVE_UPLOAD_MAX_SIZE_MB} MB。")


def build_destroy_attachment_relative_path(application: DestroyApplication, original_name: str) -> str:
    extension = Path(original_name).suffix.lower()
    stored_name = f"{timezone.now():%Y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}{extension}"
    return (
        Path("destroy-executions")
        / timezone.now().strftime("%Y%m")
        / f"application_{application.id}"
        / stored_name
    ).as_posix()


def create_destroy_execution_attachments(
    *,
    execution_record: DestroyExecutionRecord,
    attachment_files: list,
    operator_id: int,
) -> None:
    attachments_to_create: list[DestroyExecutionAttachment] = []
    for uploaded_file in attachment_files:
        validate_destroy_attachment(uploaded_file)
        relative_path = build_destroy_attachment_relative_path(execution_record.application, uploaded_file.name)
        saved_path = default_storage.save(relative_path, uploaded_file)
        attachments_to_create.append(
            DestroyExecutionAttachment(
                execution_record=execution_record,
                file_name=Path(uploaded_file.name).name,
                file_path=saved_path,
                file_size=uploaded_file.size,
                uploaded_by=operator_id,
            )
        )
    if attachments_to_create:
        DestroyExecutionAttachment.objects.bulk_create(attachments_to_create)


def validate_destroy_application_creation(*, archive: ArchiveRecord) -> None:
    if archive.status != ArchiveStatus.ON_SHELF:
        raise ValidationError("仅已上架档案允许发起销毁申请。")

    if archive.current_borrow_id:
        raise ValidationError("当前档案存在借阅占用，不能发起销毁申请。")

    has_active_borrow = BorrowApplication.objects.filter(
        archive=archive,
        status__in=ACTIVE_BORROW_APPLICATION_STATUSES,
    ).exists()
    if has_active_borrow:
        raise ValidationError("当前档案存在进行中的借阅流程，不能发起销毁申请。")

    has_active_destroy = DestroyApplication.objects.filter(
        archive=archive,
        status__in=ACTIVE_DESTROY_APPLICATION_STATUSES,
    ).exists()
    if has_active_destroy:
        raise ValidationError("当前档案已存在进行中的销毁申请。")


@transaction.atomic
def create_destroy_application(
    *,
    archive: ArchiveRecord,
    reason: str,
    basis: str,
    operator,
) -> DestroyApplication:
    if not is_archive_manager_user(operator):
        raise ValidationError("当前用户缺少发起销毁申请的权限。")

    validate_destroy_application_creation(archive=archive)
    approver = resolve_destroy_approver()
    application = DestroyApplication.objects.create(
        application_no=build_destroy_application_no(),
        archive=archive,
        applicant=operator,
        applicant_dept=operator.dept,
        reason=reason,
        basis=basis,
        status=DestroyApplicationStatus.PENDING_APPROVAL,
        current_approver=approver,
        submitted_at=timezone.now(),
        created_by=operator.id,
        updated_by=operator.id,
    )

    transition_archive_status(
        archive=archive,
        next_status=ArchiveStatus.DESTROY_PENDING,
        operator_id=operator.id,
        remark=f"发起销毁申请：{application.application_no}",
    )
    notify_destroy_application_submitted(application, approver)

    logger.info(
        "创建销毁申请",
        extra={
            "application_id": application.id,
            "application_no": application.application_no,
            "archive_id": archive.id,
            "applicant_id": operator.id,
            "approver_id": approver.id,
        },
    )
    record_audit_log(
        module_name="DESTRUCTION",
        action_code="DESTROY_APPLICATION_CREATE",
        description="发起档案销毁申请并进入管理员审批。",
        user=operator,
        biz_type="destroy_application",
        biz_id=application.id,
        target_repr=application.application_no,
        extra_data={"archive_id": archive.id, "approver_id": approver.id},
    )
    return application


@transaction.atomic
def approve_destroy_application(
    *,
    application: DestroyApplication,
    approver,
    action: str,
    opinion: str | None = None,
) -> DestroyApplication:
    if application.status != DestroyApplicationStatus.PENDING_APPROVAL:
        raise ValidationError("当前销毁申请状态不允许执行审批。")

    if not can_user_approve_destroy_application(approver, application):
        raise ValidationError("当前用户不是该销毁申请的审批人。")

    DestroyApprovalRecord.objects.create(
        application=application,
        approver=approver,
        action=action,
        opinion=opinion,
    )

    application.current_approver = None
    application.updated_by = approver.id
    if action == DestroyApprovalAction.APPROVE:
        application.status = DestroyApplicationStatus.APPROVED
        application.approved_at = timezone.now()
        application.rejected_at = None
        application.reject_reason = None
        application.save(
            update_fields=[
                "current_approver",
                "status",
                "approved_at",
                "rejected_at",
                "reject_reason",
                "updated_by",
                "updated_at",
            ]
        )
        notify_destroy_application_result(application, True, opinion)
    else:
        application.status = DestroyApplicationStatus.REJECTED
        application.rejected_at = timezone.now()
        application.reject_reason = opinion or "审批驳回"
        application.save(
            update_fields=[
                "current_approver",
                "status",
                "rejected_at",
                "reject_reason",
                "updated_by",
                "updated_at",
            ]
        )
        transition_archive_status(
            archive=application.archive,
            next_status=ArchiveStatus.ON_SHELF,
            operator_id=approver.id,
            remark=f"销毁申请驳回：{application.application_no}",
        )
        notify_destroy_application_result(application, False, opinion)

    logger.info(
        "处理销毁审批",
        extra={
            "application_id": application.id,
            "application_no": application.application_no,
            "approver_id": approver.id,
            "action": action,
        },
    )
    record_audit_log(
        module_name="DESTRUCTION",
        action_code="DESTROY_APPLICATION_APPROVE",
        description="处理档案销毁审批。",
        user=approver,
        biz_type="destroy_application",
        biz_id=application.id,
        target_repr=application.application_no,
        extra_data={"action": action, "opinion": opinion},
    )
    return application


@transaction.atomic
def execute_destroy_application(
    *,
    application: DestroyApplication,
    operator,
    execution_note: str,
    attachment_files: list,
) -> DestroyApplication:
    if application.status != DestroyApplicationStatus.APPROVED:
        raise ValidationError("仅审批通过的销毁申请允许执行销毁。")

    if not can_user_execute_destroy_application(operator, application):
        raise ValidationError("当前用户缺少销毁执行权限。")

    if hasattr(application, "execution_record"):
        raise ValidationError("当前销毁申请已完成执行，不能重复处理。")

    archive = application.archive
    if archive.status != ArchiveStatus.DESTROY_PENDING:
        raise ValidationError("当前档案不在待销毁状态，不能执行销毁。")

    executed_at = timezone.now()
    execution_record = DestroyExecutionRecord.objects.create(
        application=application,
        archive=archive,
        operator=operator,
        executed_at=executed_at,
        execution_note=execution_note,
        location_snapshot=archive.location.full_location_code if archive.location else None,
        archive_snapshot_json=build_archive_snapshot(archive),
    )
    create_destroy_execution_attachments(
        execution_record=execution_record,
        attachment_files=attachment_files,
        operator_id=operator.id,
    )

    transition_archive_status(
        archive=archive,
        next_status=ArchiveStatus.DESTROYED,
        operator_id=operator.id,
        remark=f"执行销毁：{application.application_no}",
    )

    application.status = DestroyApplicationStatus.EXECUTED
    application.executed_at = executed_at
    application.updated_by = operator.id
    application.save(update_fields=["status", "executed_at", "updated_by", "updated_at"])
    notify_destroy_application_executed(application, operator)

    logger.info(
        "执行档案销毁",
        extra={
            "application_id": application.id,
            "application_no": application.application_no,
            "execution_record_id": execution_record.id,
            "operator_id": operator.id,
            "attachment_count": len(attachment_files),
        },
    )
    record_audit_log(
        module_name="DESTRUCTION",
        action_code="DESTROY_EXECUTE",
        description="执行档案销毁并保存执行留痕。",
        user=operator,
        biz_type="destroy_application",
        biz_id=application.id,
        target_repr=application.application_no,
        extra_data={"execution_record_id": execution_record.id, "attachment_count": len(attachment_files)},
    )
    return application
