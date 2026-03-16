import shutil
from datetime import datetime, time, timedelta
from time import perf_counter
from typing import Any

from django.conf import settings
from django.db import connections
from django.db.models import Case, Count, IntegerField, Max, Q, Value, When
from django.db.models.functions import TruncDate
from django.db.utils import DatabaseError
from django.utils import timezone
from redis import Redis
from redis.exceptions import RedisError

from apps.archives.models import ArchiveRecord, ArchiveStatus
from apps.archives.services import filter_archive_queryset_by_user_scope
from apps.audit.services import build_audit_summary
from apps.borrowing.models import BorrowApplication, BorrowApplicationStatus, BorrowReturnStatus
from apps.borrowing.services import is_archive_manager_user
from apps.destruction.models import DestroyApplication, DestroyApplicationStatus
from apps.destruction.services import is_admin_or_auditor_user as is_destroy_admin_or_auditor_user
from apps.notifications.models import NotificationType, SystemNotification
from apps.notifications.services import build_notification_summary, resolve_notification_route_path
from apps.reports.services import ReportFilters, build_report_summary

HEALTH_VERSION = "0.1.0"


def build_health_payload(*, include_message: bool) -> dict[str, str]:
    payload = _build_base_payload(status="ok")

    if include_message:
        payload["message"] = "岚仓档案数字化与流转系统后端已启动"

    return payload


def build_health_detail_payload() -> dict[str, Any]:
    checks = {
        "database": check_database_health(),
        "redis": check_redis_health(),
        "storage": check_storage_health(),
    }

    payload = _build_base_payload(status=resolve_health_status(checks))
    payload["checks"] = checks
    return payload


def build_dashboard_payload(user) -> dict[str, Any]:
    archive_queryset = filter_archive_queryset_by_user_scope(
        ArchiveRecord.objects.select_related("responsible_dept"),
        user,
    ).distinct()
    notification_summary = build_notification_summary(user)
    recent_notifications = _build_recent_notification_items(user)

    if _is_borrower_only_user(user):
        return _build_borrower_dashboard_payload(
            user=user,
            archive_queryset=archive_queryset,
            notification_summary=notification_summary,
            recent_notifications=recent_notifications,
        )

    return _build_staff_dashboard_payload(
        user=user,
        archive_queryset=archive_queryset,
        notification_summary=notification_summary,
        recent_notifications=recent_notifications,
    )


def check_database_health() -> dict[str, Any]:
    started_at = perf_counter()

    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError as exc:
        return {
            "status": "error",
            "message": f"数据库连接异常：{exc}",
        }

    return {
        "status": "ok",
        "message": "数据库连接正常。",
        "latency_ms": round((perf_counter() - started_at) * 1000, 2),
    }


def check_redis_health() -> dict[str, Any]:
    started_at = perf_counter()

    try:
        client = Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        client.ping()
    except (RedisError, ValueError) as exc:
        return {
            "status": "error",
            "message": f"Redis 连接异常：{exc}",
        }

    return {
        "status": "ok",
        "message": "Redis 连接正常。",
        "latency_ms": round((perf_counter() - started_at) * 1000, 2),
    }


def check_storage_health() -> dict[str, Any]:
    media_path = settings.MEDIA_ROOT
    usage_target = media_path if media_path.exists() else media_path.parent
    total, used, free = shutil.disk_usage(usage_target)
    usage_percent = round((used / total) * 100, 2) if total else 0.0

    if usage_percent >= settings.SYSTEM_STORAGE_CRITICAL_PERCENT:
        status = "error"
        message = f"媒体目录所在磁盘使用率过高，当前为 {usage_percent}%。"
    elif usage_percent >= settings.SYSTEM_STORAGE_WARNING_PERCENT:
        status = "warning"
        message = f"媒体目录所在磁盘使用率接近阈值，当前为 {usage_percent}%。"
    else:
        status = "ok"
        message = "媒体目录所在磁盘容量充足。"

    return {
        "status": status,
        "message": message,
        "usage_percent": usage_percent,
        "free_gb": round(free / (1024 ** 3), 2),
    }


def resolve_health_status(checks: dict[str, dict[str, Any]]) -> str:
    statuses = {check["status"] for check in checks.values()}
    if "error" in statuses:
        return "error"
    if "warning" in statuses:
        return "warning"
    return "ok"


def _build_base_payload(*, status: str) -> dict[str, str]:
    return {
        "service": "backend",
        "status": status,
        "time": timezone.now().isoformat(),
        "version": HEALTH_VERSION,
    }


def _build_dashboard_card(
    *,
    key: str,
    label: str,
    value: int,
    caption: str,
    tone: str = "default",
    route_path: str | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "caption": caption,
        "tone": tone,
        "route_path": route_path,
    }


def _build_dashboard_section(
    *,
    key: str,
    title: str,
    description: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "description": description,
        "items": items,
    }


def _build_dashboard_trend_section(
    *,
    key: str,
    title: str,
    description: str,
    unit: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "description": description,
        "unit": unit,
        "items": items,
    }


def _build_dashboard_list_item(
    *,
    key: str,
    title: str,
    description: str,
    meta: str,
    tone: str = "default",
    badge: str | None = None,
    route_path: str | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "description": description,
        "meta": meta,
        "tone": tone,
        "badge": badge,
        "route_path": route_path,
    }


def _build_dashboard_trend_item(
    *,
    date_value,
    value: int,
    unit: str,
    tone: str,
) -> dict[str, Any]:
    weekday_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return {
        "label": date_value.strftime("%m-%d"),
        "value": value,
        "caption": f"{weekday_labels[date_value.weekday()]} | {value}{unit}",
        "tone": tone,
    }


def _format_dashboard_datetime(value) -> str:
    if not value:
        return "-"
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")


def _resolve_dashboard_sort_value(value) -> float:
    if not value:
        return 0.0
    return timezone.localtime(value).timestamp()


def _resolve_notification_item_route(notification: SystemNotification) -> str:
    return resolve_notification_route_path(notification)


def _resolve_notification_item_tone(notification: SystemNotification) -> str:
    if notification.is_read:
        return "default"
    if notification.notification_type == NotificationType.BORROW_REMINDER:
        return "danger"
    if notification.notification_type in {
        NotificationType.BORROW_APPROVAL,
        NotificationType.RETURN_CONFIRM,
        NotificationType.DESTROY_APPROVAL,
    }:
        return "warning"
    return "primary"


def _build_recent_notification_items(user) -> list[dict[str, Any]]:
    notification_type_labels = {
        NotificationType.BORROW_APPROVAL: "借阅审批",
        NotificationType.BORROW_REMINDER: "催还提醒",
        NotificationType.RETURN_CONFIRM: "归还确认",
        NotificationType.DESTROY_APPROVAL: "销毁审批",
        NotificationType.SYSTEM: "系统通知",
    }
    notifications = SystemNotification.objects.filter(user_id=user.id).order_by("-created_at", "-id")[:5]
    items: list[dict[str, Any]] = []

    for notification in notifications:
        items.append(
            _build_dashboard_list_item(
                key=f"notification_{notification.id}",
                title=notification.title,
                description=notification.content,
                meta=f"{'未读' if not notification.is_read else '已读'} | {_format_dashboard_datetime(notification.created_at)}",
                tone=_resolve_notification_item_tone(notification),
                badge=notification_type_labels.get(notification.notification_type, notification.notification_type),
                route_path=_resolve_notification_item_route(notification),
            )
        )

    return items


def _build_recent_trend_dates() -> list:
    today = timezone.localdate()
    return [today - timedelta(days=offset) for offset in range(6, -1, -1)]


def _build_grouped_borrow_counts(*, queryset, field_name: str, days: list) -> dict:
    date_set = set(days)
    grouped_rows = (
        queryset.exclude(**{f"{field_name}__isnull": True})
        .annotate(trend_day=TruncDate(field_name, tzinfo=timezone.get_current_timezone()))
        .values("trend_day")
        .annotate(total=Count("id"))
        .order_by()
    )
    return {
        row["trend_day"]: row["total"]
        for row in grouped_rows
        if row["trend_day"] in date_set
    }


def _build_overdue_snapshot_counts(*, queryset, days: list) -> dict:
    snapshot_counts: dict[Any, int] = {}
    current_timezone = timezone.get_current_timezone()

    for date_value in days:
        day_end = timezone.make_aware(
            datetime.combine(date_value + timedelta(days=1), time.min),
            current_timezone,
        )
        snapshot_counts[date_value] = queryset.filter(
            checkout_at__lt=day_end,
            expected_return_at__lt=day_end,
        ).filter(
            Q(returned_at__isnull=True) | Q(returned_at__gte=day_end),
        ).count()

    return snapshot_counts


def _build_dashboard_trend_sections(*, borrow_queryset) -> list[dict[str, Any]]:
    trend_dates = _build_recent_trend_dates()
    submitted_counts = _build_grouped_borrow_counts(
        queryset=borrow_queryset,
        field_name="submitted_at",
        days=trend_dates,
    )
    returned_counts = _build_grouped_borrow_counts(
        queryset=borrow_queryset.filter(returned_at__isnull=False),
        field_name="returned_at",
        days=trend_dates,
    )
    overdue_snapshot_counts = _build_overdue_snapshot_counts(
        queryset=borrow_queryset.filter(checkout_at__isnull=False),
        days=trend_dates,
    )

    return [
        _build_dashboard_trend_section(
            key="borrow_submitted_trend",
            title="近 7 天借阅申请",
            description="跟踪最近一周新提交的借阅申请量，便于判断审批入口是否会出现堆积。",
            unit="件",
            items=[
                _build_dashboard_trend_item(
                    date_value=date_value,
                    value=submitted_counts.get(date_value, 0),
                    unit="件",
                    tone="primary" if submitted_counts.get(date_value, 0) else "default",
                )
                for date_value in trend_dates
            ],
        ),
        _build_dashboard_trend_section(
            key="borrow_returned_trend",
            title="近 7 天完成归还",
            description="观察最近一周已经完成归还确认的记录数量，评估归还闭环处理效率。",
            unit="件",
            items=[
                _build_dashboard_trend_item(
                    date_value=date_value,
                    value=returned_counts.get(date_value, 0),
                    unit="件",
                    tone="success" if returned_counts.get(date_value, 0) else "default",
                )
                for date_value in trend_dates
            ],
        ),
        _build_dashboard_trend_section(
            key="borrow_overdue_trend",
            title="近 7 天超期在借",
            description="按每日收盘口径统计当日仍处于超期状态的借阅记录，用于识别催还压力是否持续升高。",
            unit="件",
            items=[
                _build_dashboard_trend_item(
                    date_value=date_value,
                    value=overdue_snapshot_counts.get(date_value, 0),
                    unit="件",
                    tone="danger" if overdue_snapshot_counts.get(date_value, 0) else "success",
                )
                for date_value in trend_dates
            ],
        ),
    ]


def _build_borrower_pending_task_items(my_applications) -> list[dict[str, Any]]:
    prioritized_applications = (
        my_applications.select_related("archive")
        .filter(
            status__in=[
                BorrowApplicationStatus.OVERDUE,
                BorrowApplicationStatus.CHECKED_OUT,
                BorrowApplicationStatus.REJECTED,
                BorrowApplicationStatus.PENDING_APPROVAL,
                BorrowApplicationStatus.APPROVED,
            ]
        )
        .annotate(
            dashboard_priority=Case(
                When(status=BorrowApplicationStatus.OVERDUE, then=Value(0)),
                When(status=BorrowApplicationStatus.CHECKED_OUT, then=Value(1)),
                When(status=BorrowApplicationStatus.REJECTED, then=Value(2)),
                When(status=BorrowApplicationStatus.PENDING_APPROVAL, then=Value(3)),
                When(status=BorrowApplicationStatus.APPROVED, then=Value(4)),
                default=Value(9),
                output_field=IntegerField(),
            )
        )
        .order_by("dashboard_priority", "-overdue_days", "expected_return_at", "-submitted_at", "-id")[:5]
    )
    items: list[dict[str, Any]] = []

    for application in prioritized_applications:
        route_path = f"/borrowing/applications?applicationId={application.id}"
        badge = "借阅跟进"
        tone = "default"
        description = f"{application.archive.title} | 单号 {application.application_no}"
        meta = f"预计归还 {_format_dashboard_datetime(application.expected_return_at)}"

        if application.status == BorrowApplicationStatus.OVERDUE:
            badge = "超期归还"
            tone = "danger"
            route_path = f"/borrowing/returns?applicationId={application.id}&mode=submit"
            description = f"{application.archive.title} | 已超期 {application.overdue_days} 天，请尽快提交归还。"
        elif application.status == BorrowApplicationStatus.CHECKED_OUT:
            badge = "待归还"
            tone = "warning"
            route_path = f"/borrowing/returns?applicationId={application.id}&mode=submit"
            description = f"{application.archive.title} | 已出库借阅中，等待提交归还材料。"
        elif application.status == BorrowApplicationStatus.REJECTED:
            badge = "待补正"
            tone = "warning"
            meta = f"驳回后重提 | {_format_dashboard_datetime(application.updated_at)}"
            description = f"{application.archive.title} | 当前申请已驳回，补充说明后可重新提交。"
        elif application.status == BorrowApplicationStatus.PENDING_APPROVAL:
            badge = "审批中"
            tone = "default"
            meta = f"提交时间 {_format_dashboard_datetime(application.submitted_at or application.created_at)}"
            description = f"{application.archive.title} | 已提交申请，等待审批负责人处理。"
        elif application.status == BorrowApplicationStatus.APPROVED:
            badge = "待出库"
            tone = "primary"
            meta = f"审批通过 {_format_dashboard_datetime(application.approved_at or application.updated_at)}"
            description = f"{application.archive.title} | 审批已通过，等待档案员办理出库。"

        items.append(
            _build_dashboard_list_item(
                key=f"borrow_task_{application.id}",
                title=application.application_no,
                description=description,
                meta=meta,
                tone=tone,
                badge=badge,
                route_path=route_path,
            )
        )

    return items


def _build_staff_pending_task_items(*, user, manage_archives: bool, can_view_destruction: bool) -> list[dict[str, Any]]:
    task_candidates: list[tuple[int, Any, dict[str, Any]]] = []

    borrow_approvals = (
        BorrowApplication.objects.select_related("archive", "applicant")
        .filter(
            status=BorrowApplicationStatus.PENDING_APPROVAL,
            current_approver_id=user.id,
        )
        .order_by("submitted_at", "id")[:5]
    )
    for application in borrow_approvals:
        task_candidates.append(
            (
                0,
                application.submitted_at or application.created_at,
                _build_dashboard_list_item(
                    key=f"borrow_approval_{application.id}",
                    title=application.application_no,
                    description=f"{application.archive.title} | 申请人：{application.applicant.real_name}",
                    meta=f"借阅审批 | 提交时间 {_format_dashboard_datetime(application.submitted_at or application.created_at)}",
                    tone="warning",
                    badge="借阅审批",
                    route_path=f"/borrowing/approvals?applicationId={application.id}",
                ),
            )
        )

    if manage_archives:
        checkout_applications = (
            BorrowApplication.objects.select_related("archive", "applicant")
            .filter(status=BorrowApplicationStatus.APPROVED)
            .order_by("approved_at", "id")[:5]
        )
        for application in checkout_applications:
            task_candidates.append(
                (
                    2,
                    application.approved_at or application.updated_at,
                    _build_dashboard_list_item(
                        key=f"borrow_checkout_{application.id}",
                        title=application.application_no,
                        description=f"{application.archive.title} | 申请人：{application.applicant.real_name}",
                        meta=f"待出库 | 审批通过 {_format_dashboard_datetime(application.approved_at or application.updated_at)}",
                        tone="warning",
                        badge="待出库",
                        route_path=f"/borrowing/checkout?applicationId={application.id}",
                    ),
                )
            )

        return_applications = (
            BorrowApplication.objects.select_related("archive", "applicant", "return_record")
            .filter(return_record__return_status=BorrowReturnStatus.SUBMITTED)
            .distinct()
            .order_by("return_record__returned_at", "id")[:5]
        )
        for application in return_applications:
            task_candidates.append(
                (
                    1,
                    application.return_record.returned_at,
                    _build_dashboard_list_item(
                        key=f"borrow_return_{application.id}",
                        title=application.application_no,
                        description=f"{application.archive.title} | 归还人：{application.applicant.real_name}",
                        meta=f"归还验收 | 提交时间 {_format_dashboard_datetime(application.return_record.returned_at)}",
                        tone="warning",
                        badge="归还验收",
                        route_path=f"/borrowing/returns?applicationId={application.id}&mode=confirm",
                    ),
                )
            )

    if can_view_destruction:
        destroy_approvals = (
            DestroyApplication.objects.select_related("archive", "applicant")
            .filter(
                status=DestroyApplicationStatus.PENDING_APPROVAL,
                current_approver_id=user.id,
            )
            .order_by("submitted_at", "id")[:5]
        )
        for application in destroy_approvals:
            task_candidates.append(
                (
                    3,
                    application.submitted_at or application.created_at,
                    _build_dashboard_list_item(
                        key=f"destroy_approval_{application.id}",
                        title=application.application_no,
                        description=f"{application.archive.title} | 申请人：{application.applicant.real_name}",
                        meta=f"销毁审批 | 提交时间 {_format_dashboard_datetime(application.submitted_at or application.created_at)}",
                        tone="danger",
                        badge="销毁审批",
                        route_path=f"/destruction/applications?applicationId={application.id}",
                    ),
                )
            )

    if manage_archives:
        destroy_executes = (
            DestroyApplication.objects.select_related("archive", "applicant")
            .filter(status=DestroyApplicationStatus.APPROVED)
            .order_by("approved_at", "id")[:5]
        )
        for application in destroy_executes:
            task_candidates.append(
                (
                    4,
                    application.approved_at or application.updated_at,
                    _build_dashboard_list_item(
                        key=f"destroy_execute_{application.id}",
                        title=application.application_no,
                        description=f"{application.archive.title} | 申请人：{application.applicant.real_name}",
                        meta=f"执行销毁 | 审批通过 {_format_dashboard_datetime(application.approved_at or application.updated_at)}",
                        tone="warning",
                        badge="执行销毁",
                        route_path=f"/destruction/applications?applicationId={application.id}",
                    ),
                )
            )

    ordered_items = sorted(
        task_candidates,
        key=lambda item: (item[0], -_resolve_dashboard_sort_value(item[1]), item[2]["key"]),
    )
    return [item[2] for item in ordered_items[:5]]


def _has_any_role(user, role_codes: set[str]) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if not hasattr(user, "roles"):
        return False
    return user.roles.filter(role_code__in=role_codes, status=True).exists()


def _is_borrower_only_user(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False) or not hasattr(user, "roles"):
        return False

    active_role_codes = set(user.roles.filter(status=True).values_list("role_code", flat=True))
    return active_role_codes == {"BORROWER"}


def _build_borrower_dashboard_payload(
    *,
    user,
    archive_queryset,
    notification_summary: dict[str, int],
    recent_notifications: list[dict[str, Any]],
) -> dict[str, Any]:
    my_applications = BorrowApplication.objects.filter(applicant_id=user.id)
    pending_approval_count = my_applications.filter(status=BorrowApplicationStatus.PENDING_APPROVAL).count()
    approved_wait_checkout_count = my_applications.filter(status=BorrowApplicationStatus.APPROVED).count()
    active_borrows = my_applications.filter(
        status__in=[BorrowApplicationStatus.CHECKED_OUT, BorrowApplicationStatus.OVERDUE],
    )
    pending_returns = active_borrows.count()
    overdue_returns = my_applications.filter(is_overdue=True).count()
    rejected_applications = my_applications.filter(status=BorrowApplicationStatus.REJECTED).count()
    returned_count = my_applications.filter(status=BorrowApplicationStatus.RETURNED).count()
    longest_overdue_days = (
        my_applications.filter(is_overdue=True)
        .aggregate(max_overdue_days=Max("overdue_days"))
        .get("max_overdue_days")
        or 0
    )
    business_unread_count = max(notification_summary["unread_count"] - notification_summary["reminder_unread_count"], 0)
    trend_sections = _build_dashboard_trend_sections(borrow_queryset=my_applications)

    priority_focus = _build_dashboard_card(
        key="pending_returns",
        label="优先处理待归还档案",
        value=pending_returns,
        caption="已出库但尚未完成归还确认的档案需要尽快提交归还材料。",
        tone="warning" if pending_returns else "success",
        route_path="/borrowing/returns",
    )
    if overdue_returns > 0:
        priority_focus = _build_dashboard_card(
            key="overdue_returns",
            label="优先处理超期归还",
            value=overdue_returns,
            caption="当前存在超期借阅记录，建议先进入归还中心处理。",
            tone="danger",
            route_path="/borrowing/returns",
        )
    elif rejected_applications > 0:
        priority_focus = _build_dashboard_card(
            key="rejected_applications",
            label="补正并重新提交申请",
            value=rejected_applications,
            caption="被驳回的申请需要补充用途说明或重新选择档案。",
            tone="warning",
            route_path="/borrowing/applications",
        )
    elif notification_summary["unread_count"] > 0:
        priority_focus = _build_dashboard_card(
            key="unread_notifications",
            label="查看待处理通知",
            value=notification_summary["unread_count"],
            caption="审批结果、催还提醒和系统通知建议优先处理。",
            tone="danger",
            route_path="/notifications/messages",
        )

    workflow_sections = [
        _build_dashboard_section(
            key="borrow_flow",
            title="我的借阅流程",
            description="用一组流程节点确认申请、出库、归还和完成状态是否顺畅闭环。",
            items=[
                _build_dashboard_card(
                    key="pending_approval_count",
                    label="待审批",
                    value=pending_approval_count,
                    caption="已提交申请、等待审批负责人处理的记录。",
                    tone="default",
                    route_path="/borrowing/applications",
                ),
                _build_dashboard_card(
                    key="approved_wait_checkout_count",
                    label="待出库",
                    value=approved_wait_checkout_count,
                    caption="审批已通过，等待档案员办理出库的记录。",
                    tone="warning" if approved_wait_checkout_count else "success",
                    route_path="/borrowing/applications",
                ),
                _build_dashboard_card(
                    key="active_borrows_flow",
                    label="借阅中",
                    value=active_borrows.count(),
                    caption="已出库且尚未完成归还确认的借阅单。",
                    tone="warning" if active_borrows.count() else "success",
                    route_path="/borrowing/returns",
                ),
                _build_dashboard_card(
                    key="returned_count",
                    label="已完成",
                    value=returned_count,
                    caption="已归还并完成入库确认的历史借阅单。",
                    tone="success",
                    route_path="/borrowing/applications",
                ),
            ],
        ),
        _build_dashboard_section(
            key="notice_scope",
            title="提醒与访问范围",
            description="确认当前账号可发起申请的业务范围，以及通知中心中还未处理的提醒数量。",
            items=[
                _build_dashboard_card(
                    key="visible_archives_scope",
                    label="可申请档案范围",
                    value=archive_queryset.exclude(status=ArchiveStatus.DESTROYED).count(),
                    caption="当前账号在借阅申请中可选择的档案范围数量。",
                    tone="primary",
                    route_path="/borrowing/applications",
                ),
                _build_dashboard_card(
                    key="reminder_unread_count_scope",
                    label="催还提醒",
                    value=notification_summary["reminder_unread_count"],
                    caption="未读催还提醒数量，超期记录会优先进入这里。",
                    tone="danger" if notification_summary["reminder_unread_count"] else "success",
                    route_path="/notifications/messages",
                ),
                _build_dashboard_card(
                    key="business_unread_count",
                    label="业务通知",
                    value=business_unread_count,
                    caption="审批结果、系统消息等非催还类通知未读数量。",
                    tone="warning" if business_unread_count else "success",
                    route_path="/notifications/messages",
                ),
                _build_dashboard_card(
                    key="longest_overdue_days",
                    label="最长超期天数",
                    value=longest_overdue_days,
                    caption="当前借阅单中最长的超期天数，用于判断处理紧急程度。",
                    tone="danger" if longest_overdue_days else "success",
                    route_path="/borrowing/returns",
                ),
            ],
        ),
    ]

    signal_cards = [
        _build_dashboard_card(
            key="pending_returns_signal",
            label="待归还提交",
            value=pending_returns,
            caption="仍在借出的档案数量，建议优先处理。",
            tone="warning" if pending_returns else "success",
            route_path="/borrowing/returns",
        ),
        _build_dashboard_card(
            key="overdue_returns_signal",
            label="超期借阅",
            value=overdue_returns,
            caption="超期借阅会同步进入催还提醒并记录通知留痕。",
            tone="danger" if overdue_returns else "success",
            route_path="/borrowing/returns",
        ),
        _build_dashboard_card(
            key="rejected_applications_signal",
            label="待补正申请",
            value=rejected_applications,
            caption="被驳回的申请可直接回到借阅中心补充后重提。",
            tone="default",
            route_path="/borrowing/applications",
        ),
        _build_dashboard_card(
            key="unread_notifications_signal",
            label="通知中心待办",
            value=notification_summary["unread_count"],
            caption="未读通知总量，含催还、审批结果与系统消息。",
            tone="danger" if notification_summary["unread_count"] else "success",
            route_path="/notifications/messages",
        ),
    ]

    return {
        "headline": "我的档案业务工作台",
        "subtitle": "聚焦个人借阅、归还、通知和可访问档案范围，避免进入与当前职责无关的系统配置页面。",
        "priority_focus": priority_focus,
        "summary_cards": [
            _build_dashboard_card(
                key="visible_archives",
                label="可查询档案",
                value=archive_queryset.exclude(status=ArchiveStatus.DESTROYED).count(),
                caption="当前账号按密级和数据范围可以检索到的档案数量。",
                tone="primary",
                route_path="/borrowing/applications",
            ),
            _build_dashboard_card(
                key="my_applications",
                label="我的申请",
                value=my_applications.count(),
                caption="已提交的借阅申请总数，含已完成和处理中记录。",
                tone="default",
                route_path="/borrowing/applications",
            ),
            _build_dashboard_card(
                key="active_borrows",
                label="当前在借",
                value=active_borrows.count(),
                caption="已经出库但尚未完成归还确认的借阅记录。",
                tone="warning",
                route_path="/borrowing/returns",
            ),
            _build_dashboard_card(
                key="unread_notifications",
                label="未读通知",
                value=notification_summary["unread_count"],
                caption="包括审批结果、催还提醒和系统通知。",
                tone="danger" if notification_summary["unread_count"] else "success",
                route_path="/notifications/messages",
            ),
        ],
        "todo_cards": [
            _build_dashboard_card(
                key="pending_returns",
                label="待归还",
                value=pending_returns,
                caption="请优先处理已出库且尚未提交归还的档案。",
                tone="warning",
                route_path="/borrowing/returns",
            ),
            _build_dashboard_card(
                key="overdue_returns",
                label="已超期",
                value=overdue_returns,
                caption="超期记录会同步进入催还提醒和通知中心。",
                tone="danger" if overdue_returns else "success",
                route_path="/borrowing/returns",
            ),
            _build_dashboard_card(
                key="rejected_applications",
                label="驳回待重提",
                value=rejected_applications,
                caption="被驳回的申请需要补充用途或重新选择档案后再提交。",
                tone="default",
                route_path="/borrowing/applications",
            ),
            _build_dashboard_card(
                key="reminder_unread_count",
                label="催还提醒",
                value=notification_summary["reminder_unread_count"],
                caption="提醒类通知未读数量，建议优先查看。",
                tone="danger" if notification_summary["reminder_unread_count"] else "success",
                route_path="/notifications/messages",
            ),
        ],
        "workflow_sections": workflow_sections,
        "trend_sections": trend_sections,
        "signal_cards": signal_cards,
        "pending_task_items": _build_borrower_pending_task_items(my_applications),
        "recent_notifications": recent_notifications,
    }


def _build_staff_dashboard_payload(
    *,
    user,
    archive_queryset,
    notification_summary: dict[str, int],
    recent_notifications: list[dict[str, Any]],
) -> dict[str, Any]:
    report_summary = build_report_summary(ReportFilters())
    audit_summary = build_audit_summary() if (_has_any_role(user, {"ADMIN", "AUDITOR"}) or getattr(user, "is_superuser", False)) else None
    manage_archives = is_archive_manager_user(user)
    can_view_destruction = is_destroy_admin_or_auditor_user(user) or manage_archives
    can_view_audit = audit_summary is not None
    can_view_reports = _has_any_role(user, {"ADMIN", "ARCHIVIST", "AUDITOR"}) or getattr(user, "is_superuser", False)
    borrow_scope_queryset = BorrowApplication.objects.filter(archive__in=archive_queryset).distinct()
    trend_sections = _build_dashboard_trend_sections(borrow_queryset=borrow_scope_queryset)

    pending_borrow_approvals = BorrowApplication.objects.filter(
        status=BorrowApplicationStatus.PENDING_APPROVAL,
        current_approver_id=user.id,
    ).count()
    pending_checkouts = BorrowApplication.objects.filter(status=BorrowApplicationStatus.APPROVED).count() if manage_archives else 0
    pending_return_confirms = BorrowApplication.objects.filter(
        return_record__return_status=BorrowReturnStatus.SUBMITTED,
    ).distinct().count() if manage_archives else 0
    pending_destroy_approvals = DestroyApplication.objects.filter(
        status=DestroyApplicationStatus.PENDING_APPROVAL,
        current_approver_id=user.id,
    ).count() if can_view_destruction else 0
    pending_destroy_executes = DestroyApplication.objects.filter(
        status=DestroyApplicationStatus.APPROVED,
    ).count() if manage_archives else 0
    pending_digitization = archive_queryset.filter(
        status__in=[ArchiveStatus.PENDING_SCAN, ArchiveStatus.PENDING_CATALOG],
    ).count()
    pending_catalog = archive_queryset.filter(status=ArchiveStatus.PENDING_CATALOG).count()
    on_shelf_archive_count = archive_queryset.filter(status=ArchiveStatus.ON_SHELF).count()
    destroyed_archive_count = archive_queryset.filter(status=ArchiveStatus.DESTROYED).count()
    overdue_borrow_count = report_summary["overdue_count"]
    utilization_rate = int(round(report_summary["archive_utilization_rate"]))

    summary_cards = [
        _build_dashboard_card(
            key="archive_total",
            label="可见档案",
            value=archive_queryset.exclude(status=ArchiveStatus.DESTROYED).count(),
            caption="按当前账号职责和数据范围可见的档案总量。",
            tone="primary",
            route_path="/archives/records",
        ),
        _build_dashboard_card(
            key="on_shelf_archives",
            label="在架档案",
            value=archive_queryset.filter(status=ArchiveStatus.ON_SHELF).count(),
            caption="当前可直接借阅或继续流转处理的在架档案数量。",
            tone="success",
            route_path="/archives/records",
        ),
        _build_dashboard_card(
            key="active_borrow_count",
            label="借阅处理中",
            value=report_summary["active_borrow_count"],
            caption="系统中仍处于审批、出库、借出或超期状态的借阅单数量。",
            tone="warning",
            route_path="/borrowing/applications",
        ),
        _build_dashboard_card(
            key="unread_notifications",
            label="未读通知",
            value=notification_summary["unread_count"],
            caption="待查看的系统通知和业务流转提醒。",
            tone="danger" if notification_summary["unread_count"] else "success",
            route_path="/notifications/messages",
        ),
    ]

    if audit_summary:
        summary_cards[2] = _build_dashboard_card(
            key="risk_audit_count",
            label="风险事件",
            value=audit_summary["failed_count"],
            caption="审计日志中失败或拒绝结果的累计数量。",
            tone="danger" if audit_summary["failed_count"] else "success",
            route_path="/audit/logs",
        )

    priority_focus = _build_dashboard_card(
        key="pending_borrow_approvals",
        label="优先处理借阅审批",
        value=pending_borrow_approvals,
        caption="当前指派给我的借阅审批任务应优先清空，避免后续出库和归还流程阻塞。",
        tone="warning" if pending_borrow_approvals else "success",
        route_path="/borrowing/approvals",
    )
    if pending_borrow_approvals > 0:
        priority_focus = _build_dashboard_card(
            key="pending_borrow_approvals",
            label="优先处理借阅审批",
            value=pending_borrow_approvals,
            caption="当前指派给我的借阅审批任务应优先清空，避免后续出库和归还流程阻塞。",
            tone="warning",
            route_path="/borrowing/approvals",
        )
    elif manage_archives and pending_return_confirms > 0:
        priority_focus = _build_dashboard_card(
            key="pending_returns",
            label="优先处理归还验收",
            value=pending_return_confirms,
            caption="已有归还材料提交，建议尽快确认并重新入库。",
            tone="warning",
            route_path="/borrowing/returns",
        )
    elif manage_archives and pending_checkouts > 0:
        priority_focus = _build_dashboard_card(
            key="pending_checkouts",
            label="优先办理待出库申请",
            value=pending_checkouts,
            caption="审批已通过的借阅单需要尽快出库，避免申请人等待。",
            tone="warning",
            route_path="/borrowing/checkout",
        )
    elif can_view_destruction and max(pending_destroy_approvals, pending_destroy_executes) > 0:
        priority_focus = _build_dashboard_card(
            key="pending_destroy_actions",
            label="优先处理销毁链路",
            value=max(pending_destroy_approvals, pending_destroy_executes),
            caption="含待审批和待执行的销毁任务，需要及时闭环并留痕。",
            tone="danger",
            route_path="/destruction/applications",
        )
    elif pending_digitization > 0:
        priority_focus = _build_dashboard_card(
            key="pending_digitization",
            label="优先跟进数字化积压",
            value=pending_digitization,
            caption="待扫描和待编目的档案会影响后续借阅、检索与标签打印。",
            tone="warning",
            route_path="/digitization/scan-tasks",
        )
    elif notification_summary["unread_count"] > 0:
        priority_focus = _build_dashboard_card(
            key="unread_notifications",
            label="查看未读通知",
            value=notification_summary["unread_count"],
            caption="通知中包含审批流转、催还、系统消息等待处理事项。",
            tone="danger",
            route_path="/notifications/messages",
        )

    first_todo_card = _build_dashboard_card(
        key="pending_borrow_approvals",
        label="待借阅审批",
        value=pending_borrow_approvals,
        caption="当前指派给我的借阅审批任务数量。",
        tone="warning",
        route_path="/borrowing/approvals",
    )
    if manage_archives and pending_borrow_approvals == 0:
        first_todo_card = _build_dashboard_card(
            key="pending_checkouts",
            label="待出库",
            value=pending_checkouts,
            caption="审批已通过但尚未办理出库的借阅申请数量。",
            tone="warning",
            route_path="/borrowing/checkout",
        )

    second_todo_card = _build_dashboard_card(
        key="pending_digitization",
        label="待数字化",
        value=pending_digitization,
        caption="仍处于待扫描或待编目的档案数量。",
        tone="default",
        route_path="/digitization/scan-tasks",
    )
    if manage_archives and pending_borrow_approvals > 0:
        second_todo_card = _build_dashboard_card(
            key="pending_checkouts",
            label="待出库",
            value=pending_checkouts,
            caption="审批已通过但尚未办理出库的借阅申请数量。",
            tone="warning",
            route_path="/borrowing/checkout",
        )

    todo_cards = [
        first_todo_card,
        second_todo_card,
        _build_dashboard_card(
            key="pending_returns",
            label="待归还验收",
            value=pending_return_confirms,
            caption="已经提交归还材料、等待档案员确认入库的记录数量。",
            tone="warning",
            route_path="/borrowing/returns",
        ),
        _build_dashboard_card(
            key="pending_destroy_actions",
            label="待销毁处理",
            value=max(pending_destroy_approvals, pending_destroy_executes),
            caption="含待审批销毁和审批通过后待执行销毁的总量。",
            tone="danger" if max(pending_destroy_approvals, pending_destroy_executes) else "success",
            route_path="/destruction/applications",
        ),
    ]

    workflow_sections: list[dict[str, Any]] = []

    if manage_archives or can_view_reports:
        archive_flow_items = [
            _build_dashboard_card(
                key="pending_scan_flow",
                label="待扫描",
                value=archive_queryset.filter(status=ArchiveStatus.PENDING_SCAN).count(),
                caption="纸质档案尚未进入扫描任务的数量。",
                tone="default",
                route_path="/digitization/scan-tasks" if manage_archives else "/reports/center",
            ),
            _build_dashboard_card(
                key="pending_catalog_flow",
                label="待编目",
                value=pending_catalog,
                caption="数字化完成但仍待补录编目字段的档案数量。",
                tone="warning" if pending_catalog else "success",
                route_path="/digitization/scan-tasks" if manage_archives else "/reports/center",
            ),
            _build_dashboard_card(
                key="on_shelf_archives_flow",
                label="在架",
                value=on_shelf_archive_count,
                caption="可继续借阅或流转处理的在架档案总量。",
                tone="success",
                route_path="/archives/records" if manage_archives else "/reports/center",
            ),
            _build_dashboard_card(
                key="destroyed_archives_flow",
                label="已销毁",
                value=destroyed_archive_count,
                caption="完成销毁登记并进入闭环记录的档案数量。",
                tone="default",
                route_path="/destruction/applications" if can_view_destruction else "/reports/center",
            ),
        ]
        workflow_sections.append(
            _build_dashboard_section(
                key="archive_flow",
                title="档案流转看板",
                description="从待扫描、待编目到在架和销毁闭环，快速判断档案主线是否积压。",
                items=archive_flow_items,
            )
        )

    borrow_flow_items = [
        _build_dashboard_card(
            key="pending_borrow_approvals_flow",
            label="待审批",
            value=pending_borrow_approvals,
            caption="当前由我处理的借阅审批任务数量。",
            tone="warning" if pending_borrow_approvals else "success",
            route_path="/borrowing/approvals" if pending_borrow_approvals or _has_any_role(user, {"ADMIN"}) else "/",
        ),
        _build_dashboard_card(
            key="pending_checkouts_flow",
            label="待出库",
            value=pending_checkouts,
            caption="审批已通过但尚未办理实体出库的借阅单。",
            tone="warning" if pending_checkouts else "success",
            route_path="/borrowing/checkout" if manage_archives else "/reports/center",
        ),
        _build_dashboard_card(
            key="pending_returns_flow",
            label="待归还验收",
            value=pending_return_confirms,
            caption="已提交归还材料、等待确认入库的借阅记录。",
            tone="warning" if pending_return_confirms else "success",
            route_path="/borrowing/returns" if manage_archives else "/reports/center",
        ),
        _build_dashboard_card(
            key="overdue_borrow_count_flow",
            label="超期借阅",
            value=overdue_borrow_count,
            caption="系统内当前仍处于超期状态的借阅单数量。",
            tone="danger" if overdue_borrow_count else "success",
            route_path="/reports/center" if can_view_reports else "/notifications/messages",
        ),
    ]
    workflow_sections.append(
        _build_dashboard_section(
            key="borrow_flow",
            title="借阅闭环看板",
            description="围绕审批、出库、归还和超期监控组织日常借阅处理顺序。",
            items=borrow_flow_items,
        )
    )

    supervision_items = [
        _build_dashboard_card(
            key="unread_notifications_signal",
            label="未读通知",
            value=notification_summary["unread_count"],
            caption="系统消息、催还提醒和流转通知待查看数量。",
            tone="danger" if notification_summary["unread_count"] else "success",
            route_path="/notifications/messages",
        ),
        _build_dashboard_card(
            key="pending_destroy_approvals_flow",
            label="待销毁审批",
            value=pending_destroy_approvals,
            caption="当前指派给我的销毁审批任务数量。",
            tone="danger" if pending_destroy_approvals else "success",
            route_path="/destruction/applications" if can_view_destruction else "/reports/center",
        ),
        _build_dashboard_card(
            key="pending_destroy_executes_flow",
            label="待执行销毁",
            value=pending_destroy_executes,
            caption="已审批通过但尚未登记执行的销毁任务数量。",
            tone="warning" if pending_destroy_executes else "success",
            route_path="/destruction/applications" if can_view_destruction else "/reports/center",
        ),
        _build_dashboard_card(
            key="risk_audit_count_signal",
            label="风险审计",
            value=audit_summary["failed_count"] if audit_summary else 0,
            caption="失败或拒绝类审计事件累计数量。",
            tone="danger" if audit_summary and audit_summary["failed_count"] else "success",
            route_path="/audit/logs" if can_view_audit else "/reports/center",
        ),
    ]
    workflow_sections.append(
        _build_dashboard_section(
            key="supervision_flow",
            title="通知与监督",
            description="把通知、销毁审批和风险审计放在一起，便于统一收口当天异常。",
            items=supervision_items,
        )
    )

    signal_cards = [
        _build_dashboard_card(
            key="utilization_rate_signal",
            label="档案利用率",
            value=utilization_rate,
            caption="有借阅记录的档案占可统计档案总量的比例，单位为百分比。",
            tone="primary",
            route_path="/reports/center",
        ),
        _build_dashboard_card(
            key="active_borrow_count_signal",
            label="借阅处理中",
            value=report_summary["active_borrow_count"],
            caption="审批、出库、借出和超期状态的借阅单总量。",
            tone="warning" if report_summary["active_borrow_count"] else "success",
            route_path="/reports/center" if can_view_reports else "/notifications/messages",
        ),
        _build_dashboard_card(
            key="pending_digitization_signal",
            label="数字化积压",
            value=pending_digitization,
            caption="待扫描和待编目档案总量，用于评估档案主数据积压。",
            tone="warning" if pending_digitization else "success",
            route_path="/digitization/scan-tasks" if manage_archives else "/reports/center",
        ),
        _build_dashboard_card(
            key="notification_reminder_signal",
            label="催还未读",
            value=notification_summary["reminder_unread_count"],
            caption="催还类通知未读数量，适合联动借阅和通知中心处理。",
            tone="danger" if notification_summary["reminder_unread_count"] else "success",
            route_path="/notifications/messages",
        ),
    ]

    return {
        "headline": "档案业务工作台",
        "subtitle": "围绕档案流转、借阅闭环、风险提醒和通知待办组织日常操作，减少在多个页面之间反复切换。",
        "priority_focus": priority_focus,
        "summary_cards": summary_cards,
        "todo_cards": todo_cards,
        "workflow_sections": workflow_sections,
        "trend_sections": trend_sections,
        "signal_cards": signal_cards,
        "pending_task_items": _build_staff_pending_task_items(
            user=user,
            manage_archives=manage_archives,
            can_view_destruction=can_view_destruction,
        ),
        "recent_notifications": recent_notifications,
    }
