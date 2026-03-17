import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import record_audit_log
from apps.archives.models import ArchiveRecord, ArchiveStatus, ArchiveStorageLocation
from apps.archives.services import transition_archive_status, update_archive_record, user_can_view_archive_sensitive_fields
from apps.borrowing.models import (
    BorrowApplication,
    BorrowApplicationStatus,
    BorrowApprovalAction,
    BorrowApprovalRecord,
    BorrowCheckoutRecord,
    BorrowHandoverType,
    BorrowReminderChannel,
    BorrowReminderRecord,
    BorrowReminderSendStatus,
    BorrowReminderType,
    BorrowReturnAttachment,
    BorrowReturnAttachmentType,
    BorrowReturnRecord,
    BorrowReturnStatus,
)
from apps.notifications.models import EmailTask, EmailTaskStatus, NotificationType
from apps.notifications.services import create_email_task, create_system_notification, dispatch_email_task


logger = logging.getLogger(__name__)
User = get_user_model()

ACTIVE_BORROW_APPLICATION_STATUSES = {
    BorrowApplicationStatus.PENDING_APPROVAL,
    BorrowApplicationStatus.APPROVED,
    BorrowApplicationStatus.CHECKED_OUT,
    BorrowApplicationStatus.OVERDUE,
}
RETURN_ALLOWED_APPLICATION_STATUSES = {
    BorrowApplicationStatus.CHECKED_OUT,
    BorrowApplicationStatus.OVERDUE,
}
ALLOWED_RETURN_ATTACHMENT_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
BIZ_TYPE_BORROW_APPLICATION = "borrow_application"
BORROW_READ_PERMISSION_CODES = {
    "menu.borrow_center",
    "menu.borrow_approval",
    "menu.borrow_checkout",
    "menu.borrow_return",
    "menu.report_center",
    "menu.audit_log",
    "button.borrow.create",
    "button.borrow.approve",
    "button.borrow.checkout",
    "button.borrow.return.submit",
    "button.borrow.return.confirm",
}
BORROW_READ_FALLBACK_ROLES = {"ADMIN", "ARCHIVIST", "BORROWER", "AUDITOR"}
BORROW_CENTER_READ_PERMISSION_CODES = {"menu.borrow_center", "button.borrow.create"}
BORROW_APPROVAL_READ_PERMISSION_CODES = {"menu.borrow_approval", "button.borrow.approve"}
BORROW_CHECKOUT_READ_PERMISSION_CODES = {"menu.borrow_checkout", "button.borrow.checkout"}
BORROW_RETURN_SUBMIT_READ_PERMISSION_CODES = {"menu.borrow_return", "button.borrow.return.submit"}
BORROW_RETURN_CONFIRM_READ_PERMISSION_CODES = {"menu.borrow_return", "button.borrow.return.confirm"}
BORROW_ALL_READ_PERMISSION_CODES = {
    "menu.borrow_approval",
    "menu.borrow_checkout",
    "button.borrow.return.confirm",
    "menu.report_center",
    "menu.audit_log",
}


def _has_any_role(user, role_codes: set[str]) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if not hasattr(user, "roles"):
        return False
    return user.roles.filter(role_code__in=role_codes, status=True).exists()


def _has_any_permission(user, permission_codes: set[str]) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if not hasattr(user, "roles"):
        return False
    return user.roles.filter(
        status=True,
        permissions__permission_code__in=permission_codes,
        permissions__status=True,
    ).exists()


def is_archive_manager_user(user) -> bool:
    return _has_any_role(user, {"ADMIN", "ARCHIVIST"}) or _has_any_permission(
        user,
        {"button.borrow.checkout", "button.borrow.return.confirm", "button.notification.reminder.dispatch"},
    )


def is_admin_or_auditor_user(user) -> bool:
    return _has_any_role(user, {"ADMIN", "AUDITOR"})


def has_borrow_center_access(user) -> bool:
    return _has_any_role(user, {"ADMIN", "ARCHIVIST", "BORROWER"}) or _has_any_permission(
        user,
        BORROW_CENTER_READ_PERMISSION_CODES,
    )


def has_borrow_approval_access(user) -> bool:
    return _has_any_role(user, {"ADMIN"}) or _has_any_permission(user, BORROW_APPROVAL_READ_PERMISSION_CODES)


def has_borrow_checkout_access(user) -> bool:
    return is_archive_manager_user(user) or _has_any_permission(user, BORROW_CHECKOUT_READ_PERMISSION_CODES)


def has_borrow_return_submit_access(user) -> bool:
    return _has_any_role(user, {"ADMIN", "ARCHIVIST", "BORROWER"}) or _has_any_permission(
        user,
        BORROW_RETURN_SUBMIT_READ_PERMISSION_CODES,
    )


def has_borrow_return_confirm_access(user) -> bool:
    return is_archive_manager_user(user) or _has_any_permission(user, BORROW_RETURN_CONFIRM_READ_PERMISSION_CODES)


def has_borrow_all_access(user) -> bool:
    return _has_any_role(user, {"ADMIN", "ARCHIVIST", "AUDITOR"}) or _has_any_permission(
        user,
        BORROW_ALL_READ_PERMISSION_CODES,
    )


def filter_borrow_queryset_by_read_scope(
    queryset,
    *,
    user,
    scope: str | None,
    notified_application_ids,
):
    normalized_scope = (scope or "").strip().lower()
    notified_application_ids = list(notified_application_ids or [])

    if normalized_scope == "mine":
        if not has_borrow_center_access(user) and not has_borrow_return_submit_access(user):
            raise PermissionDenied("当前账号无权查看个人借阅申请列表。")
        return queryset.filter(applicant_id=user.id)

    if normalized_scope == "approval":
        if not has_borrow_approval_access(user):
            raise PermissionDenied("当前账号无权查看待审批借阅申请。")
        return queryset.filter(
            current_approver_id=user.id,
            status=BorrowApplicationStatus.PENDING_APPROVAL,
        )

    if normalized_scope == "checkout":
        if not has_borrow_checkout_access(user):
            raise PermissionDenied("当前账号无权查看待出库借阅申请。")
        return queryset.filter(status=BorrowApplicationStatus.APPROVED)

    if normalized_scope == "return":
        if not has_borrow_return_confirm_access(user):
            raise PermissionDenied("当前账号无权查看待确认归还记录。")
        return queryset.filter(return_record__return_status=BorrowReturnStatus.SUBMITTED)

    if normalized_scope == "all":
        if not has_borrow_all_access(user):
            raise PermissionDenied("当前账号无权查看全部借阅申请。")
        return queryset

    if has_borrow_all_access(user):
        return queryset

    visibility_filter = Q(applicant_id=user.id) | Q(current_approver_id=user.id)
    if notified_application_ids:
        visibility_filter |= Q(id__in=notified_application_ids)
    if has_borrow_checkout_access(user):
        visibility_filter |= Q(status=BorrowApplicationStatus.APPROVED)
    if has_borrow_return_confirm_access(user):
        visibility_filter |= Q(return_record__return_status=BorrowReturnStatus.SUBMITTED)
    return queryset.filter(visibility_filter)


def can_user_approve_borrow_application(user, application: BorrowApplication) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if not has_borrow_approval_access(user):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return application.current_approver_id == user.id


def can_user_submit_borrow_return(user, application: BorrowApplication) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if not has_borrow_return_submit_access(user):
        return False
    if is_archive_manager_user(user):
        return True
    return application.applicant_id == user.id


def can_user_confirm_borrow_return(user) -> bool:
    return has_borrow_return_confirm_access(user)


def build_borrow_application_no() -> str:
    return f"BOR{timezone.now():%Y%m%d%H%M%S}{uuid.uuid4().hex[:6].upper()}"


def build_borrow_application_display(application: BorrowApplication) -> str:
    return f"{application.archive.archive_code}《{application.archive.title}》"


def notify_borrow_application_submitted(application: BorrowApplication, approver) -> None:
    expected_return_at = timezone.localtime(application.expected_return_at).strftime("%Y-%m-%d %H:%M")
    create_system_notification(
        user=approver,
        notification_type=NotificationType.BORROW_APPROVAL,
        title="档案借阅待审批",
        content=(
            f"{application.applicant.real_name} 提交了档案 {build_borrow_application_display(application)} 的借阅申请，"
            f"预计归还时间为 {expected_return_at}，请及时完成审批。"
        ),
        biz_type=BIZ_TYPE_BORROW_APPLICATION,
        biz_id=application.id,
    )


def notify_borrow_application_result(
    application: BorrowApplication,
    *,
    approved: bool,
    opinion: str | None = None,
) -> None:
    title = "档案借阅审批已通过" if approved else "档案借阅审批已驳回"
    result_text = (
        "审批已通过，请联系档案员办理出库。"
        if approved
        else f"审批已驳回，原因：{opinion or application.reject_reason or '无'}。"
    )
    create_system_notification(
        user=application.applicant,
        notification_type=NotificationType.BORROW_APPROVAL,
        title=title,
        content=f"档案 {build_borrow_application_display(application)} 的借阅申请处理完成，{result_text}",
        biz_type=BIZ_TYPE_BORROW_APPLICATION,
        biz_id=application.id,
    )


def notify_borrow_return_submitted(application: BorrowApplication, returned_by) -> None:
    archive_managers = (
        User.objects.filter(status=True)
        .filter(
            Q(roles__role_code="ADMIN", roles__status=True)
            | Q(roles__role_code="ARCHIVIST", roles__status=True)
            | Q(
                roles__permissions__permission_code="button.borrow.return.confirm",
                roles__permissions__status=True,
                roles__status=True,
            )
        )
        .distinct()
        .order_by("id")
    )
    for receiver in archive_managers:
        create_system_notification(
            user=receiver,
            notification_type=NotificationType.RETURN_CONFIRM,
            title="档案归还待确认",
            content=(
                f"{returned_by.real_name} 已提交档案 {build_borrow_application_display(application)} 的归还申请，"
                "请核对交接凭证并完成入库确认。"
            ),
            biz_type=BIZ_TYPE_BORROW_APPLICATION,
            biz_id=application.id,
        )


def notify_borrow_return_result(
    application: BorrowApplication,
    *,
    approved: bool,
    confirm_note: str | None = None,
) -> None:
    return_record = getattr(application, "return_record", None)
    recipients: dict[int, object] = {application.applicant_id: application.applicant}
    returned_by = getattr(return_record, "returned_by_user", None)
    if returned_by and returned_by.id != application.applicant_id:
        recipients[returned_by.id] = returned_by

    title = "档案归还已确认入库" if approved else "档案归还验收未通过"
    result_text = (
        "归还验收已通过，档案已重新入库。"
        if approved
        else f"归还验收未通过，原因：{confirm_note or '无'}。"
    )
    for receiver in recipients.values():
        create_system_notification(
            user=receiver,
            notification_type=NotificationType.RETURN_CONFIRM,
            title=title,
            content=f"档案 {build_borrow_application_display(application)} 的归还处理完成，{result_text}",
            biz_type=BIZ_TYPE_BORROW_APPLICATION,
            biz_id=application.id,
        )


def resolve_borrow_approver(applicant) -> User:
    approver_id = getattr(applicant.dept, "approver_user_id", None)
    if approver_id:
        approver = User.objects.filter(id=approver_id, status=True).first()
        if approver:
            return approver

    fallback_approver = (
        User.objects.filter(status=True, roles__role_code="ADMIN", roles__status=True)
        .distinct()
        .order_by("id")
        .first()
    )
    if fallback_approver:
        return fallback_approver

    raise ValidationError("当前部门未配置有效审批负责人，且系统中不存在可回退的管理员审批人。")


def calculate_overdue_days(expected_return_at, compare_at) -> int:
    if compare_at <= expected_return_at:
        return 0
    return max((compare_at.date() - expected_return_at.date()).days, 1)


def sync_borrow_application_overdue_state(application: BorrowApplication) -> BorrowApplication:
    if application.status not in RETURN_ALLOWED_APPLICATION_STATUSES or application.returned_at:
        return application

    now = timezone.now()
    overdue_days = calculate_overdue_days(application.expected_return_at, now)
    next_status = BorrowApplicationStatus.OVERDUE if overdue_days > 0 else BorrowApplicationStatus.CHECKED_OUT
    next_is_overdue = overdue_days > 0
    changed_fields: list[str] = []

    if application.status != next_status:
        application.status = next_status
        changed_fields.append("status")
    if application.is_overdue != next_is_overdue:
        application.is_overdue = next_is_overdue
        changed_fields.append("is_overdue")
    if application.overdue_days != overdue_days:
        application.overdue_days = overdue_days
        changed_fields.append("overdue_days")

    if changed_fields:
        changed_fields.append("updated_at")
        application.save(update_fields=changed_fields)

    return application


def sync_overdue_borrow_applications() -> None:
    applications = BorrowApplication.objects.filter(
        status__in=[BorrowApplicationStatus.CHECKED_OUT, BorrowApplicationStatus.OVERDUE],
        returned_at__isnull=True,
    ).iterator()
    for application in applications:
        sync_borrow_application_overdue_state(application)


def resolve_borrow_reminder_type(application: BorrowApplication, now) -> str | None:
    expected_date = timezone.localtime(application.expected_return_at).date()
    today = timezone.localtime(now).date()
    day_delta = (expected_date - today).days

    before_due_days = int(getattr(settings, "BORROW_REMINDER_BEFORE_DUE_DAYS", 3))
    if day_delta == before_due_days:
        return BorrowReminderType.BEFORE_DUE
    if day_delta == 0:
        return BorrowReminderType.DUE_TODAY
    if day_delta < 0:
        return BorrowReminderType.OVERDUE
    return None


def build_borrow_reminder_title(reminder_type: str) -> str:
    label_map = {
        BorrowReminderType.BEFORE_DUE: "借阅到期前提醒",
        BorrowReminderType.DUE_TODAY: "借阅到期当天提醒",
        BorrowReminderType.OVERDUE: "借阅超期提醒",
    }
    return label_map.get(reminder_type, "借阅催还提醒")


def build_borrow_reminder_content(application: BorrowApplication, reminder_type: str, now) -> str:
    expected_time = timezone.localtime(application.expected_return_at).strftime("%Y-%m-%d %H:%M")
    archive_name = f"{application.archive.archive_code}《{application.archive.title}》"
    if reminder_type == BorrowReminderType.BEFORE_DUE:
        before_due_days = int(getattr(settings, "BORROW_REMINDER_BEFORE_DUE_DAYS", 3))
        return f"您借阅的档案 {archive_name} 将于 {expected_time} 到期，请在 {before_due_days} 天内完成归还。"
    if reminder_type == BorrowReminderType.DUE_TODAY:
        return f"您借阅的档案 {archive_name} 今日到期，请尽快提交归还并上传交接凭证。"

    overdue_days = calculate_overdue_days(application.expected_return_at, now)
    return f"您借阅的档案 {archive_name} 已超期 {overdue_days} 天，请立即归还。"


def build_borrow_reminder_receivers(application: BorrowApplication, reminder_type: str, now) -> list:
    receiver_map: dict[int, object] = {application.applicant_id: application.applicant}
    if reminder_type != BorrowReminderType.OVERDUE:
        return list(receiver_map.values())

    overdue_days = calculate_overdue_days(application.expected_return_at, now)
    escalate_days = int(getattr(settings, "BORROW_REMINDER_ESCALATE_DAYS", 3))
    if overdue_days < escalate_days:
        return list(receiver_map.values())

    approver = resolve_borrow_approver(application.applicant)
    receiver_map[approver.id] = approver

    archive_managers = (
        User.objects.filter(status=True)
        .filter(Q(roles__role_code="ADMIN") | Q(roles__role_code="ARCHIVIST"), roles__status=True)
        .distinct()
    )
    for user in archive_managers:
        receiver_map[user.id] = user

    return list(receiver_map.values())


def reminder_already_sent_today(
    *,
    application: BorrowApplication,
    reminder_type: str,
    channel: str,
    receiver_user=None,
    receiver_email: str | None = None,
    now=None,
) -> bool:
    current_time = now or timezone.now()
    queryset = BorrowReminderRecord.objects.filter(
        application=application,
        reminder_type=reminder_type,
        channel=channel,
        sent_at__date=timezone.localtime(current_time).date(),
    )
    if receiver_user:
        queryset = queryset.filter(receiver_user=receiver_user)
    elif receiver_email:
        queryset = queryset.filter(receiver_email=receiver_email)
    else:
        queryset = queryset.filter(receiver_user__isnull=True)
    return queryset.exists()


def create_site_reminder_record(
    *,
    application: BorrowApplication,
    receiver_user,
    reminder_type: str,
    content: str,
) -> BorrowReminderRecord:
    notification = create_system_notification(
        user=receiver_user,
        notification_type=NotificationType.BORROW_REMINDER,
        title=build_borrow_reminder_title(reminder_type),
        content=content,
        biz_type=BIZ_TYPE_BORROW_APPLICATION,
        biz_id=application.id,
    )
    return BorrowReminderRecord.objects.create(
        application=application,
        reminder_type=reminder_type,
        channel=BorrowReminderChannel.SITE,
        receiver_user=receiver_user,
        send_status=BorrowReminderSendStatus.SUCCESS,
        sent_at=timezone.now(),
        content_summary=notification.title,
        notification=notification,
    )


def map_email_task_status_to_borrow_reminder_status(email_task_status: str) -> str:
    status_mapping = {
        EmailTaskStatus.PENDING: BorrowReminderSendStatus.PENDING,
        EmailTaskStatus.RUNNING: BorrowReminderSendStatus.RUNNING,
        EmailTaskStatus.SUCCESS: BorrowReminderSendStatus.SUCCESS,
        EmailTaskStatus.FAILED: BorrowReminderSendStatus.FAILED,
    }
    return status_mapping.get(email_task_status, BorrowReminderSendStatus.PENDING)


def sync_borrow_reminder_records_for_email_task(*, email_task: EmailTask) -> None:
    update_kwargs = {
        "send_status": map_email_task_status_to_borrow_reminder_status(email_task.send_status),
        "updated_at": timezone.now(),
    }
    if email_task.sent_at:
        update_kwargs["sent_at"] = email_task.sent_at
    BorrowReminderRecord.objects.filter(email_task=email_task).update(**update_kwargs)


def create_email_reminder_record(
    *,
    application: BorrowApplication,
    receiver_user,
    reminder_type: str,
    content: str,
) -> BorrowReminderRecord | None:
    receiver_email = (receiver_user.email or "").strip()
    if not receiver_email:
        return None

    email_task = create_email_task(
        receiver_user=receiver_user,
        receiver_email=receiver_email,
        subject=build_borrow_reminder_title(reminder_type),
        content=content,
        biz_type=BIZ_TYPE_BORROW_APPLICATION,
        biz_id=application.id,
    )
    reminder_record = BorrowReminderRecord.objects.create(
        application=application,
        reminder_type=reminder_type,
        channel=BorrowReminderChannel.EMAIL,
        receiver_user=receiver_user,
        receiver_email=receiver_email,
        send_status=map_email_task_status_to_borrow_reminder_status(email_task.send_status),
        sent_at=timezone.now(),
        content_summary=email_task.subject,
        email_task=email_task,
    )
    dispatch_email_task(email_task)
    email_task.refresh_from_db()
    sync_borrow_reminder_records_for_email_task(email_task=email_task)
    reminder_record.refresh_from_db()
    return reminder_record


@transaction.atomic
def dispatch_borrow_reminder_for_application(application: BorrowApplication, now=None) -> list[BorrowReminderRecord]:
    current_time = now or timezone.now()
    application = sync_borrow_application_overdue_state(application)
    if application.status not in RETURN_ALLOWED_APPLICATION_STATUSES:
        return []

    reminder_type = resolve_borrow_reminder_type(application, current_time)
    if not reminder_type:
        return []

    content = build_borrow_reminder_content(application, reminder_type, current_time)
    receivers = build_borrow_reminder_receivers(application, reminder_type, current_time)
    created_records: list[BorrowReminderRecord] = []

    for receiver_user in receivers:
        if not reminder_already_sent_today(
            application=application,
            reminder_type=reminder_type,
            channel=BorrowReminderChannel.SITE,
            receiver_user=receiver_user,
            now=current_time,
        ):
            created_records.append(
                create_site_reminder_record(
                    application=application,
                    receiver_user=receiver_user,
                    reminder_type=reminder_type,
                    content=content,
                )
            )

        receiver_email = (receiver_user.email or "").strip()
        if receiver_email and not reminder_already_sent_today(
            application=application,
            reminder_type=reminder_type,
            channel=BorrowReminderChannel.EMAIL,
            receiver_user=receiver_user,
            receiver_email=receiver_email,
            now=current_time,
        ):
            email_record = create_email_reminder_record(
                application=application,
                receiver_user=receiver_user,
                reminder_type=reminder_type,
                content=content,
            )
            if email_record:
                created_records.append(email_record)

    if created_records:
        logger.info(
            "借阅催还提醒发送完成",
            extra={
                "application_id": application.id,
                "application_no": application.application_no,
                "reminder_type": reminder_type,
                "record_count": len(created_records),
            },
        )
    return created_records


def dispatch_due_borrow_reminders(*, now=None) -> list[BorrowReminderRecord]:
    current_time = now or timezone.now()
    reminder_records: list[BorrowReminderRecord] = []
    applications = (
        BorrowApplication.objects.select_related("archive", "applicant", "applicant_dept")
        .filter(status__in=[BorrowApplicationStatus.CHECKED_OUT, BorrowApplicationStatus.OVERDUE])
        .order_by("id")
    )
    for application in applications:
        reminder_records.extend(dispatch_borrow_reminder_for_application(application, current_time))
    return reminder_records


def validate_borrow_application_creation(
    *,
    archive: ArchiveRecord,
    applicant,
    expected_return_at,
) -> None:
    if expected_return_at <= timezone.now():
        raise ValidationError("预计归还时间必须晚于当前时间。")

    if archive.status != ArchiveStatus.ON_SHELF:
        raise ValidationError("仅已上架档案允许发起借阅申请。")

    if archive.status in {ArchiveStatus.BORROWED, ArchiveStatus.DESTROY_PENDING, ArchiveStatus.DESTROYED, ArchiveStatus.FROZEN}:
        raise ValidationError("当前档案状态不允许借阅。")

    if archive.current_borrow_id:
        raise ValidationError("当前档案已有进行中的借阅流程。")

    if not user_can_view_archive_sensitive_fields(applicant, archive):
        raise ValidationError("当前账号密级不足，不能申请该档案借阅。")

    existing_application = BorrowApplication.objects.filter(
        archive=archive,
        status__in=ACTIVE_BORROW_APPLICATION_STATUSES,
    ).exists()
    if existing_application:
        raise ValidationError("当前档案已存在进行中的借阅申请，暂不可重复申请。")

    applicant_has_overdue = BorrowApplication.objects.filter(
        applicant=applicant,
        status=BorrowApplicationStatus.OVERDUE,
    ).exists()
    if applicant_has_overdue:
        raise ValidationError("当前账号存在超期未归还借阅记录，暂不允许再次申请。")


@transaction.atomic
def create_borrow_application(
    *,
    archive: ArchiveRecord,
    purpose: str,
    expected_return_at,
    operator,
) -> BorrowApplication:
    sync_overdue_borrow_applications()
    validate_borrow_application_creation(
        archive=archive,
        applicant=operator,
        expected_return_at=expected_return_at,
    )

    approver = resolve_borrow_approver(operator)
    application = BorrowApplication.objects.create(
        application_no=build_borrow_application_no(),
        archive=archive,
        applicant=operator,
        applicant_dept=operator.dept,
        purpose=purpose,
        expected_return_at=expected_return_at,
        status=BorrowApplicationStatus.PENDING_APPROVAL,
        current_approver=approver,
        submitted_at=timezone.now(),
        created_by=operator.id,
        updated_by=operator.id,
    )
    notify_borrow_application_submitted(application, approver)
    logger.info(
        "创建借阅申请",
        extra={
            "application_id": application.id,
            "application_no": application.application_no,
            "archive_id": archive.id,
            "applicant_id": operator.id,
            "approver_id": approver.id,
        },
    )
    record_audit_log(
        module_name="BORROWING",
        action_code="BORROW_APPLICATION_CREATE",
        description="创建借阅申请并提交部门负责人审批。",
        user=operator,
        biz_type="borrow_application",
        biz_id=application.id,
        target_repr=application.application_no,
        extra_data={"archive_id": archive.id, "approver_id": approver.id},
    )
    return application


@transaction.atomic
def approve_borrow_application(
    *,
    application: BorrowApplication,
    approver,
    action: str,
    opinion: str | None = None,
) -> BorrowApplication:
    if application.status != BorrowApplicationStatus.PENDING_APPROVAL:
        raise ValidationError("当前借阅申请状态不允许执行审批。")

    if not can_user_approve_borrow_application(approver, application):
        raise ValidationError("当前用户不是该借阅申请的审批人。")

    BorrowApprovalRecord.objects.create(
        application=application,
        approver=approver,
        action=action,
        opinion=opinion,
    )

    application.current_approver = None
    application.updated_by = approver.id
    if action == BorrowApprovalAction.APPROVE:
        application.status = BorrowApplicationStatus.APPROVED
        application.approved_at = timezone.now()
        application.rejected_at = None
        application.reject_reason = None
    else:
        application.status = BorrowApplicationStatus.REJECTED
        application.rejected_at = timezone.now()
        application.reject_reason = opinion or "审批驳回"
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
    notify_borrow_application_result(
        application,
        approved=action == BorrowApprovalAction.APPROVE,
        opinion=opinion,
    )

    logger.info(
        "处理借阅审批",
        extra={
            "application_id": application.id,
            "application_no": application.application_no,
            "approver_id": approver.id,
            "action": action,
        },
    )
    record_audit_log(
        module_name="BORROWING",
        action_code="BORROW_APPLICATION_APPROVE",
        description="处理借阅申请审批。",
        user=approver,
        biz_type="borrow_application",
        biz_id=application.id,
        target_repr=application.application_no,
        extra_data={"action": action, "opinion": opinion},
    )
    return application


@transaction.atomic
def register_borrow_checkout(
    *,
    application: BorrowApplication,
    operator,
    checkout_note: str | None = None,
) -> BorrowApplication:
    if hasattr(application, "checkout_record"):
        raise ValidationError("当前借阅申请已办理过出库。")

    if application.status != BorrowApplicationStatus.APPROVED:
        raise ValidationError("仅审批通过的借阅申请允许办理出库。")

    if not is_archive_manager_user(operator):
        raise ValidationError("当前用户缺少出库登记权限。")

    archive = application.archive
    if archive.status != ArchiveStatus.ON_SHELF:
        raise ValidationError("当前档案不在可出库状态。")

    location_snapshot = archive.location.full_location_code if archive.location else None
    checkout_record = BorrowCheckoutRecord.objects.create(
        application=application,
        archive=archive,
        borrower=application.applicant,
        operator=operator,
        checkout_at=timezone.now(),
        expected_return_at=application.expected_return_at,
        location_snapshot=location_snapshot,
        checkout_note=checkout_note,
    )

    application.status = BorrowApplicationStatus.CHECKED_OUT
    application.checkout_at = checkout_record.checkout_at
    application.updated_by = operator.id
    application.save(update_fields=["status", "checkout_at", "updated_by", "updated_at"])

    transition_archive_status(
        archive=archive,
        next_status=ArchiveStatus.BORROWED,
        operator_id=operator.id,
        current_borrow_id=application.id,
        remark=f"借阅出库：{application.application_no}",
    )

    logger.info(
        "办理借阅出库",
        extra={
            "application_id": application.id,
            "application_no": application.application_no,
            "checkout_record_id": checkout_record.id,
            "operator_id": operator.id,
        },
    )
    record_audit_log(
        module_name="BORROWING",
        action_code="BORROW_CHECKOUT",
        description="办理借阅出库登记。",
        user=operator,
        biz_type="borrow_application",
        biz_id=application.id,
        target_repr=application.application_no,
        extra_data={"archive_id": archive.id, "checkout_note": checkout_note},
    )
    return application


def validate_return_attachment(uploaded_file) -> str:
    file_name = Path(uploaded_file.name).name
    extension = Path(file_name).suffix.lower().lstrip(".")
    if extension not in ALLOWED_RETURN_ATTACHMENT_EXTENSIONS:
        raise ValidationError(f"不支持的归还附件格式：{extension or '未知'}。")

    max_size = settings.ARCHIVE_UPLOAD_MAX_SIZE_MB * 1024 * 1024
    if uploaded_file.size > max_size:
        raise ValidationError(f"单个归还附件大小不能超过 {settings.ARCHIVE_UPLOAD_MAX_SIZE_MB} MB。")

    return extension


def build_return_attachment_relative_path(
    application: BorrowApplication,
    attachment_type: str,
    original_name: str,
) -> str:
    extension = Path(original_name).suffix.lower()
    stored_name = f"{timezone.now():%Y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}{extension}"
    return (
        Path("borrow-returns")
        / timezone.now().strftime("%Y%m")
        / f"application_{application.id}"
        / attachment_type.lower()
        / stored_name
    ).as_posix()


def replace_return_attachments(
    *,
    application: BorrowApplication,
    return_record: BorrowReturnRecord,
    photo_files: list,
    handover_files: list,
    operator_id: int,
) -> None:
    for attachment in list(return_record.attachments.all()):
        if attachment.file_path:
            default_storage.delete(attachment.file_path)
        attachment.delete()

    attachments_to_create: list[BorrowReturnAttachment] = []
    for attachment_type, files in (
        (BorrowReturnAttachmentType.PHOTO, photo_files),
        (BorrowReturnAttachmentType.HANDOVER_DOC, handover_files),
    ):
        for uploaded_file in files:
            validate_return_attachment(uploaded_file)
            relative_path = build_return_attachment_relative_path(application, attachment_type, uploaded_file.name)
            saved_path = default_storage.save(relative_path, uploaded_file)
            attachments_to_create.append(
                BorrowReturnAttachment(
                    return_record=return_record,
                    attachment_type=attachment_type,
                    file_name=Path(uploaded_file.name).name,
                    file_path=saved_path,
                    file_size=uploaded_file.size,
                    uploaded_by=operator_id,
                )
            )

    BorrowReturnAttachment.objects.bulk_create(attachments_to_create)


def resolve_handover_type(photo_files: list, handover_files: list) -> str:
    if photo_files and handover_files:
        return BorrowHandoverType.BOTH
    if photo_files:
        return BorrowHandoverType.PHOTO
    if handover_files:
        return BorrowHandoverType.DOCUMENT
    raise ValidationError("归还时至少需要上传照片或交接单中的一种。")


@transaction.atomic
def submit_borrow_return(
    *,
    application: BorrowApplication,
    returned_by,
    photo_files: list,
    handover_files: list,
    handover_note: str | None = None,
) -> BorrowApplication:
    sync_borrow_application_overdue_state(application)
    if application.status not in RETURN_ALLOWED_APPLICATION_STATUSES:
        raise ValidationError("当前借阅申请状态不允许提交归还。")

    if not can_user_submit_borrow_return(returned_by, application):
        raise ValidationError("当前用户不能提交该借阅申请的归还。")

    handover_type = resolve_handover_type(photo_files, handover_files)
    return_record, _ = BorrowReturnRecord.objects.get_or_create(
        application=application,
        defaults={
            "archive": application.archive,
            "returned_by_user": returned_by,
            "handover_type": handover_type,
            "handover_note": handover_note,
            "returned_at": timezone.now(),
            "return_status": BorrowReturnStatus.SUBMITTED,
        },
    )

    if return_record.return_status == BorrowReturnStatus.CONFIRMED:
        raise ValidationError("当前借阅申请已完成归还确认，不能重复提交。")

    return_record.archive = application.archive
    return_record.returned_by_user = returned_by
    return_record.return_status = BorrowReturnStatus.SUBMITTED
    return_record.handover_type = handover_type
    return_record.handover_note = handover_note
    return_record.returned_at = timezone.now()
    return_record.received_by_user = None
    return_record.confirmed_at = None
    return_record.location_after_return = None
    return_record.confirm_note = None
    return_record.save(
        update_fields=[
            "archive",
            "returned_by_user",
            "return_status",
            "handover_type",
            "handover_note",
            "returned_at",
            "received_by_user",
            "confirmed_at",
            "location_after_return",
            "confirm_note",
            "updated_at",
        ]
    )
    replace_return_attachments(
        application=application,
        return_record=return_record,
        photo_files=photo_files,
        handover_files=handover_files,
        operator_id=returned_by.id,
    )
    notify_borrow_return_submitted(application, returned_by)

    logger.info(
        "提交借阅归还",
        extra={
            "application_id": application.id,
            "application_no": application.application_no,
            "return_record_id": return_record.id,
            "returned_by_user_id": returned_by.id,
        },
    )
    record_audit_log(
        module_name="BORROWING",
        action_code="BORROW_RETURN_SUBMIT",
        description="提交借阅归还并上传交接凭证。",
        user=returned_by,
        biz_type="borrow_application",
        biz_id=application.id,
        target_repr=application.application_no,
        extra_data={"photo_count": len(photo_files), "handover_count": len(handover_files)},
    )
    return application


@transaction.atomic
def confirm_borrow_return(
    *,
    application: BorrowApplication,
    operator,
    approved: bool,
    confirm_note: str | None = None,
    location_after_return: ArchiveStorageLocation | None = None,
) -> BorrowApplication:
    sync_borrow_application_overdue_state(application)
    if application.status not in RETURN_ALLOWED_APPLICATION_STATUSES:
        raise ValidationError("当前借阅申请状态不允许执行归还确认。")

    if not can_user_confirm_borrow_return(operator):
        raise ValidationError("当前用户缺少归还确认权限。")

    return_record = getattr(application, "return_record", None)
    if not return_record:
        raise ValidationError("当前借阅申请尚未提交归还。")
    if return_record.return_status != BorrowReturnStatus.SUBMITTED:
        raise ValidationError("当前归还记录不是待确认状态。")

    return_record.received_by_user = operator
    return_record.confirm_note = confirm_note

    if approved:
        if location_after_return and location_after_return.id != application.archive.location_id:
            update_archive_record(
                archive=application.archive,
                validated_data={"location": location_after_return},
                operator_id=operator.id,
                revision_remark=f"归还入库调整位置：{application.application_no}",
            )
            application.archive.refresh_from_db()

        confirmed_at = timezone.now()
        actual_return_at = return_record.returned_at or confirmed_at
        overdue_days = calculate_overdue_days(application.expected_return_at, actual_return_at)

        return_record.return_status = BorrowReturnStatus.CONFIRMED
        return_record.confirmed_at = confirmed_at
        return_record.location_after_return = location_after_return or application.archive.location
        return_record.save(
            update_fields=[
                "received_by_user",
                "confirm_note",
                "return_status",
                "confirmed_at",
                "location_after_return",
                "updated_at",
            ]
        )

        application.status = BorrowApplicationStatus.RETURNED
        application.returned_at = confirmed_at
        application.is_overdue = overdue_days > 0
        application.overdue_days = overdue_days
        application.updated_by = operator.id
        application.save(
            update_fields=[
                "status",
                "returned_at",
                "is_overdue",
                "overdue_days",
                "updated_by",
                "updated_at",
            ]
        )

        transition_archive_status(
            archive=application.archive,
            next_status=ArchiveStatus.ON_SHELF,
            operator_id=operator.id,
            remark=f"归还确认入库：{application.application_no}",
        )
    else:
        return_record.return_status = BorrowReturnStatus.REJECTED
        return_record.confirmed_at = None
        return_record.save(
            update_fields=[
                "received_by_user",
                "confirm_note",
                "return_status",
                "confirmed_at",
                "updated_at",
            ]
        )
        application.updated_by = operator.id
        application.save(update_fields=["updated_by", "updated_at"])
        sync_borrow_application_overdue_state(application)
    notify_borrow_return_result(
        application,
        approved=approved,
        confirm_note=confirm_note,
    )

    logger.info(
        "处理归还确认",
        extra={
            "application_id": application.id,
            "application_no": application.application_no,
            "operator_id": operator.id,
            "approved": approved,
        },
    )
    record_audit_log(
        module_name="BORROWING",
        action_code="BORROW_RETURN_CONFIRM",
        description="处理借阅归还确认。",
        user=operator,
        biz_type="borrow_application",
        biz_id=application.id,
        target_repr=application.application_no,
        extra_data={"approved": approved, "location_after_return_id": location_after_return.id if location_after_return else None},
    )
    return application
