import csv
from dataclasses import asdict, dataclass
from io import StringIO

from django.db.models import Count, Max, Q, QuerySet

from apps.archives.models import ArchiveRecord
from apps.borrowing.models import BorrowApplication, BorrowApplicationStatus


@dataclass
class ReportFilters:
    start_date: object | None = None
    end_date: object | None = None
    applicant_dept_id: int | None = None
    archive_security_level: str | None = None
    archive_status: str | None = None
    carrier_type: str | None = None


def build_report_filters(validated_data: dict) -> ReportFilters:
    return ReportFilters(
        start_date=validated_data.get("start_date"),
        end_date=validated_data.get("end_date"),
        applicant_dept_id=validated_data.get("applicant_dept_id"),
        archive_security_level=validated_data.get("archive_security_level"),
        archive_status=validated_data.get("archive_status"),
        carrier_type=validated_data.get("carrier_type"),
    )


def apply_borrow_report_filters(queryset: QuerySet[BorrowApplication], filters: ReportFilters) -> QuerySet[BorrowApplication]:
    if filters.start_date:
        queryset = queryset.filter(created_at__date__gte=filters.start_date)
    if filters.end_date:
        queryset = queryset.filter(created_at__date__lte=filters.end_date)
    if filters.applicant_dept_id:
        queryset = queryset.filter(applicant_dept_id=filters.applicant_dept_id)
    if filters.archive_security_level:
        queryset = queryset.filter(archive__security_level=filters.archive_security_level)
    if filters.archive_status:
        queryset = queryset.filter(archive__status=filters.archive_status)
    if filters.carrier_type:
        queryset = queryset.filter(archive__carrier_type=filters.carrier_type)
    return queryset


def apply_archive_report_filters(queryset: QuerySet[ArchiveRecord], filters: ReportFilters) -> QuerySet[ArchiveRecord]:
    if filters.archive_security_level:
        queryset = queryset.filter(security_level=filters.archive_security_level)
    if filters.archive_status:
        queryset = queryset.filter(status=filters.archive_status)
    if filters.carrier_type:
        queryset = queryset.filter(carrier_type=filters.carrier_type)
    if filters.applicant_dept_id:
        queryset = queryset.filter(borrow_applications__applicant_dept_id=filters.applicant_dept_id)
    if filters.start_date:
        queryset = queryset.filter(borrow_applications__created_at__date__gte=filters.start_date)
    if filters.end_date:
        queryset = queryset.filter(borrow_applications__created_at__date__lte=filters.end_date)
    return queryset


def build_report_summary(filters: ReportFilters) -> dict:
    borrow_queryset = apply_borrow_report_filters(
        BorrowApplication.objects.select_related("archive", "applicant_dept"),
        filters,
    )
    total_borrow_count = borrow_queryset.count()
    overdue_count = borrow_queryset.filter(is_overdue=True).count()
    returned_count = borrow_queryset.filter(status=BorrowApplicationStatus.RETURNED).count()
    active_borrow_count = borrow_queryset.filter(
        status__in=[
            BorrowApplicationStatus.PENDING_APPROVAL,
            BorrowApplicationStatus.APPROVED,
            BorrowApplicationStatus.CHECKED_OUT,
            BorrowApplicationStatus.OVERDUE,
        ]
    ).count()

    archive_queryset = apply_archive_report_filters(
        ArchiveRecord.objects.all(),
        filters,
    ).distinct()
    total_archive_count = archive_queryset.count()
    utilized_archive_count = archive_queryset.filter(borrow_applications__isnull=False).distinct().count()

    overdue_rate = round((overdue_count / total_borrow_count) * 100, 2) if total_borrow_count else 0
    archive_utilization_rate = round((utilized_archive_count / total_archive_count) * 100, 2) if total_archive_count else 0

    return {
        "total_borrow_count": total_borrow_count,
        "overdue_count": overdue_count,
        "overdue_rate": overdue_rate,
        "returned_count": returned_count,
        "active_borrow_count": active_borrow_count,
        "total_archive_count": total_archive_count,
        "utilized_archive_count": utilized_archive_count,
        "archive_utilization_rate": archive_utilization_rate,
    }


def build_department_report(filters: ReportFilters) -> list[dict]:
    queryset = apply_borrow_report_filters(
        BorrowApplication.objects.select_related("applicant_dept"),
        filters,
    )
    rows = list(
        queryset.values("applicant_dept_id", "applicant_dept__dept_name")
        .annotate(
            borrow_count=Count("id"),
            overdue_count=Count("id", filter=Q(is_overdue=True)),
            returned_count=Count("id", filter=Q(status=BorrowApplicationStatus.RETURNED)),
        )
        .order_by("-borrow_count", "applicant_dept_id")
    )
    for row in rows:
        borrow_count = row["borrow_count"] or 0
        overdue_count = row["overdue_count"] or 0
        row["applicant_dept_name"] = row.pop("applicant_dept__dept_name")
        row["overdue_rate"] = round((overdue_count / borrow_count) * 100, 2) if borrow_count else 0
    return rows


def build_archive_utilization_report(filters: ReportFilters) -> list[dict]:
    queryset = apply_archive_report_filters(
        ArchiveRecord.objects.all(),
        filters,
    ).annotate(
        borrow_count=Count("borrow_applications", distinct=True),
        overdue_count=Count("borrow_applications", filter=Q(borrow_applications__is_overdue=True), distinct=True),
        returned_count=Count(
            "borrow_applications",
            filter=Q(borrow_applications__status=BorrowApplicationStatus.RETURNED),
            distinct=True,
        ),
        latest_borrowed_at=Max("borrow_applications__created_at"),
    ).order_by("-borrow_count", "id").distinct()

    rows: list[dict] = []
    for index, archive in enumerate(queryset, start=1):
        if archive.borrow_count <= 0:
            continue
        rows.append(
            {
                "rank": index,
                "archive_id": archive.id,
                "archive_code": archive.archive_code,
                "archive_title": archive.title,
                "security_level": archive.security_level,
                "status": archive.status,
                "carrier_type": archive.carrier_type,
                "borrow_count": archive.borrow_count,
                "overdue_count": archive.overdue_count,
                "returned_count": archive.returned_count,
                "latest_borrowed_at": archive.latest_borrowed_at.isoformat() if archive.latest_borrowed_at else None,
            }
        )
    return rows


def export_rows_to_csv(*, headers: list[str], rows: list[dict]) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([row.get(header, "") for header in headers])
    return buffer.getvalue()


def serialize_report_filters(filters: ReportFilters) -> dict:
    payload = asdict(filters)
    for key, value in list(payload.items()):
        if hasattr(value, "isoformat"):
            payload[key] = value.isoformat()
    return payload

