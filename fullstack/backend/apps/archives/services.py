import logging
from datetime import timedelta
from pathlib import Path

import barcode
import qrcode
from barcode.writer import ImageWriter
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.models import ArchiveFileAccessAction
from apps.audit.services import build_watermark_text, issue_archive_file_access_ticket, record_audit_log
from apps.accounts.models import DataScope, SecurityClearance
from apps.archives.models import (
    ArchiveBarcode,
    ArchiveCodeType,
    ArchiveFile,
    ArchiveFileStatus,
    ArchiveMetadataRevision,
    ArchiveRecord,
    ArchiveStorageLocation,
    ArchiveStatus,
)


logger = logging.getLogger(__name__)
User = get_user_model()

MASKED_SUMMARY_TEXT = "权限不足，摘要已脱敏。"
MASKED_RESPONSIBLE_PERSON_TEXT = "权限不足，责任者已脱敏。"
MASKED_LOCATION_TEXT = "权限不足，隐藏实体精确位置。"
MASKED_FILE_TEXT = "权限不足，文件信息已脱敏。"

SECURITY_CLEARANCE_ORDER = {
    SecurityClearance.PUBLIC: 1,
    SecurityClearance.INTERNAL: 2,
    SecurityClearance.SECRET: 3,
    SecurityClearance.CONFIDENTIAL: 4,
    SecurityClearance.TOP_SECRET: 5,
}

DATA_SCOPE_PRIORITY = {
    DataScope.SELF: 1,
    DataScope.DEPT: 2,
    DataScope.DEPT_AND_CHILD: 3,
    DataScope.ALL: 4,
}

ARCHIVE_SNAPSHOT_FIELDS = [
    "archive_code",
    "title",
    "year",
    "retention_period",
    "security_level",
    "status",
    "responsible_dept_id",
    "responsible_person",
    "formed_at",
    "keywords",
    "summary",
    "page_count",
    "carrier_type",
    "location_id",
    "current_borrow_id",
    "catalog_completed_at",
    "shelved_at",
]

ARCHIVE_STATUS_TRANSITIONS: dict[str, set[str]] = {
    ArchiveStatus.DRAFT: {ArchiveStatus.PENDING_SCAN, ArchiveStatus.PENDING_CATALOG, ArchiveStatus.FROZEN},
    ArchiveStatus.PENDING_SCAN: {ArchiveStatus.PENDING_CATALOG, ArchiveStatus.FROZEN},
    ArchiveStatus.PENDING_CATALOG: {ArchiveStatus.ON_SHELF, ArchiveStatus.FROZEN},
    ArchiveStatus.ON_SHELF: {ArchiveStatus.BORROWED, ArchiveStatus.DESTROY_PENDING, ArchiveStatus.FROZEN},
    ArchiveStatus.BORROWED: {ArchiveStatus.ON_SHELF, ArchiveStatus.FROZEN},
    ArchiveStatus.DESTROY_PENDING: {ArchiveStatus.DESTROYED, ArchiveStatus.ON_SHELF, ArchiveStatus.FROZEN},
    ArchiveStatus.DESTROYED: set(),
    ArchiveStatus.FROZEN: {
        ArchiveStatus.DRAFT,
        ArchiveStatus.PENDING_SCAN,
        ArchiveStatus.PENDING_CATALOG,
        ArchiveStatus.ON_SHELF,
        ArchiveStatus.DESTROY_PENDING,
    },
}


def _user_is_admin(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if hasattr(user, "roles"):
        return user.roles.filter(role_code="ADMIN", status=True).exists()
    return False


def _resolve_operator(operator_id: int | None):
    if not operator_id:
        return None
    return User.objects.filter(id=operator_id, status=True).first()


def resolve_user_archive_data_scope(user) -> str:
    if _user_is_admin(user):
        return DataScope.ALL

    if not user or not getattr(user, "is_authenticated", False) or not hasattr(user, "roles"):
        return DataScope.SELF

    resolved_scope = DataScope.SELF
    role_scopes = user.roles.filter(status=True).values_list("data_scope", flat=True)
    for scope in role_scopes:
        if DATA_SCOPE_PRIORITY.get(scope, 0) > DATA_SCOPE_PRIORITY[resolved_scope]:
            resolved_scope = scope
    return resolved_scope


def filter_archive_queryset_by_user_scope(queryset, user):
    if _user_is_admin(user):
        return queryset

    if not user or not getattr(user, "is_authenticated", False):
        return queryset.none()

    user_dept_id = getattr(user, "dept_id", None)
    if not user_dept_id:
        return queryset.none()

    scope = resolve_user_archive_data_scope(user)
    if scope == DataScope.ALL:
        return queryset

    own_archive_filter = Q(responsible_dept__isnull=True, created_by=user.id)
    if scope == DataScope.DEPT:
        return queryset.filter(Q(responsible_dept_id=user_dept_id) | own_archive_filter)

    if scope == DataScope.DEPT_AND_CHILD:
        user_dept = getattr(user, "dept", None)
        user_dept_path = getattr(user_dept, "dept_path", "")
        if not user_dept_path:
            return queryset.filter(Q(responsible_dept_id=user_dept_id) | own_archive_filter)

        return queryset.filter(
            Q(responsible_dept__dept_path=user_dept_path)
            | Q(responsible_dept__dept_path__startswith=f"{user_dept_path}/")
            | own_archive_filter
        )

    user_real_name = (getattr(user, "real_name", "") or "").strip()
    self_scope_filter = Q(responsible_dept_id=user_dept_id) | Q(created_by=user.id) | own_archive_filter
    # 档案主数据当前以责任部门作为主要归属单元，SELF 在档案模块按主部门收敛，
    # 同时保留本人创建或负责记录的访问能力，避免出现“有权限但完全看不到本人业务数据”的情况。
    if user_real_name:
        self_scope_filter |= Q(responsible_person=user_real_name)

    return queryset.filter(self_scope_filter)


def validate_archive_data_scope(*, archive: ArchiveRecord, user) -> None:
    accessible = filter_archive_queryset_by_user_scope(
        ArchiveRecord.objects.filter(id=archive.id),
        user,
    ).exists()
    if accessible:
        return

    raise PermissionDenied("当前账号无权访问所属范围外的档案。")


def user_can_view_archive_sensitive_fields(user, archive: ArchiveRecord) -> bool:
    if _user_is_admin(user):
        return True

    user_clearance = SECURITY_CLEARANCE_ORDER.get(
        getattr(user, "security_clearance_level", SecurityClearance.PUBLIC),
        0,
    )
    archive_clearance = SECURITY_CLEARANCE_ORDER.get(archive.security_level, 0)
    return user_clearance >= archive_clearance


def build_masked_archive_location_detail(location: ArchiveStorageLocation | None) -> dict | None:
    if not location:
        return None

    return {
        "id": location.id,
        "warehouse_name": location.warehouse_name,
        "area_name": None,
        "cabinet_code": "",
        "rack_code": "",
        "layer_code": "",
        "box_code": "",
        "full_location_code": MASKED_LOCATION_TEXT,
        "status": location.status,
        "remark": None,
        "created_by": None,
        "updated_by": None,
        "created_at": location.created_at.isoformat(),
        "updated_at": location.updated_at.isoformat(),
    }


def _normalize_snapshot_value(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def build_archive_snapshot(archive: ArchiveRecord) -> dict:
    snapshot: dict[str, object] = {}
    for field_name in ARCHIVE_SNAPSHOT_FIELDS:
        snapshot[field_name] = _normalize_snapshot_value(getattr(archive, field_name))
    return snapshot


def build_archive_changes(before_snapshot: dict, after_snapshot: dict) -> dict:
    changed_fields: dict[str, dict[str, object]] = {}
    for field_name in ARCHIVE_SNAPSHOT_FIELDS:
        before_value = before_snapshot.get(field_name)
        after_value = after_snapshot.get(field_name)
        if before_value != after_value:
            changed_fields[field_name] = {
                "before": before_value,
                "after": after_value,
            }
    return changed_fields


def create_archive_revision(
    archive: ArchiveRecord,
    changed_fields: dict,
    snapshot: dict,
    revised_by: int,
    remark: str | None = None,
) -> ArchiveMetadataRevision:
    revision_no = (
        ArchiveMetadataRevision.objects.filter(archive=archive).aggregate(max_revision=Max("revision_no"))[
            "max_revision"
        ]
        or 0
    ) + 1
    return ArchiveMetadataRevision.objects.create(
        archive=archive,
        revision_no=revision_no,
        changed_fields_json=changed_fields,
        snapshot_json=snapshot,
        remark=remark,
        revised_by=revised_by,
    )


@transaction.atomic
def create_archive_record(
    *,
    validated_data: dict,
    operator_id: int,
    revision_remark: str | None = None,
) -> ArchiveRecord:
    operator = _resolve_operator(operator_id)
    archive = ArchiveRecord.objects.create(
        **validated_data,
        created_by=operator_id,
        updated_by=operator_id,
    )
    snapshot = build_archive_snapshot(archive)
    create_archive_revision(
        archive=archive,
        changed_fields={field_name: {"before": None, "after": field_value} for field_name, field_value in snapshot.items()},
        snapshot=snapshot,
        revised_by=operator_id,
        remark=revision_remark or "创建档案记录",
    )
    record_audit_log(
        module_name="ARCHIVES",
        action_code="ARCHIVE_CREATE",
        description="创建档案主数据并生成初始修订记录。",
        user=operator,
        biz_type="archive_record",
        biz_id=archive.id,
        target_repr=archive.archive_code,
        extra_data={"status": archive.status},
    )
    logger.info("创建档案记录", extra={"archive_id": archive.id, "archive_code": archive.archive_code})
    return archive


@transaction.atomic
def update_archive_record(
    *,
    archive: ArchiveRecord,
    validated_data: dict,
    operator_id: int,
    revision_remark: str | None = None,
) -> ArchiveRecord:
    operator = _resolve_operator(operator_id)
    before_snapshot = build_archive_snapshot(archive)
    for field_name, value in validated_data.items():
        setattr(archive, field_name, value)
    archive.updated_by = operator_id
    archive.save()

    after_snapshot = build_archive_snapshot(archive)
    changed_fields = build_archive_changes(before_snapshot, after_snapshot)
    if changed_fields:
        create_archive_revision(
            archive=archive,
            changed_fields=changed_fields,
            snapshot=after_snapshot,
            revised_by=operator_id,
            remark=revision_remark or "更新档案信息",
        )
        record_audit_log(
            module_name="ARCHIVES",
            action_code="ARCHIVE_UPDATE",
            description="更新档案主数据并写入修订记录。",
            user=operator,
            biz_type="archive_record",
            biz_id=archive.id,
            target_repr=archive.archive_code,
            extra_data={"changed_fields": list(changed_fields.keys())},
        )

    logger.info("更新档案记录", extra={"archive_id": archive.id, "archive_code": archive.archive_code})
    return archive


@transaction.atomic
def transition_archive_status(
    *,
    archive: ArchiveRecord,
    next_status: str,
    operator_id: int,
    remark: str | None = None,
    current_borrow_id: int | None = None,
) -> ArchiveRecord:
    operator = _resolve_operator(operator_id)
    current_status = archive.status
    if next_status == current_status:
        raise ValidationError("档案当前已经处于目标状态。")

    allowed_statuses = ARCHIVE_STATUS_TRANSITIONS.get(current_status, set())
    if next_status not in allowed_statuses:
        raise ValidationError(f"不允许从 {archive.get_status_display()} 流转到目标状态。")

    if next_status == ArchiveStatus.BORROWED and not current_borrow_id:
        raise ValidationError("流转到借出中状态时必须提供当前借阅单 ID。")

    before_snapshot = build_archive_snapshot(archive)
    archive.status = next_status
    archive.updated_by = operator_id

    if next_status == ArchiveStatus.BORROWED:
        archive.current_borrow_id = current_borrow_id
    elif next_status in {ArchiveStatus.ON_SHELF, ArchiveStatus.DESTROYED}:
        archive.current_borrow_id = None

    if next_status == ArchiveStatus.ON_SHELF:
        current_time = timezone.now()
        archive.catalog_completed_at = archive.catalog_completed_at or current_time
        archive.shelved_at = current_time

    archive.save()

    after_snapshot = build_archive_snapshot(archive)
    create_archive_revision(
        archive=archive,
        changed_fields=build_archive_changes(before_snapshot, after_snapshot),
        snapshot=after_snapshot,
        revised_by=operator_id,
        remark=remark or f"状态流转：{current_status} -> {next_status}",
    )
    logger.info(
        "档案状态流转",
        extra={
            "archive_id": archive.id,
            "archive_code": archive.archive_code,
            "from_status": current_status,
            "to_status": next_status,
        },
    )
    record_audit_log(
        module_name="ARCHIVES",
        action_code="ARCHIVE_STATUS_TRANSITION",
        description=f"档案状态从 {current_status} 流转到 {next_status}。",
        user=operator,
        biz_type="archive_record",
        biz_id=archive.id,
        target_repr=archive.archive_code,
        extra_data={
            "from_status": current_status,
            "to_status": next_status,
            "current_borrow_id": current_borrow_id,
        },
    )
    return archive


def _ensure_media_directory(relative_dir: str) -> Path:
    target_dir = Path(settings.MEDIA_ROOT) / relative_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def _generate_barcode_image(archive: ArchiveRecord) -> str:
    target_dir = _ensure_media_directory("barcodes")
    file_base = target_dir / f"archive_{archive.id}_barcode"
    code128 = barcode.get("code128", archive.archive_code, writer=ImageWriter())
    saved_path = Path(code128.save(str(file_base)))
    return saved_path.relative_to(settings.MEDIA_ROOT).as_posix()


def _generate_qrcode_image(archive: ArchiveRecord) -> str:
    target_dir = _ensure_media_directory("qrcodes")
    file_path = target_dir / f"archive_{archive.id}_qrcode.png"
    image = qrcode.make(archive.archive_code)
    image.save(file_path)
    return file_path.relative_to(settings.MEDIA_ROOT).as_posix()


@transaction.atomic
def generate_archive_codes(*, archive: ArchiveRecord, operator_id: int) -> list[ArchiveBarcode]:
    operator = _resolve_operator(operator_id)
    image_path_map = {
        ArchiveCodeType.BARCODE: _generate_barcode_image(archive),
        ArchiveCodeType.QRCODE: _generate_qrcode_image(archive),
    }

    barcode_records: list[ArchiveBarcode] = []
    for code_type, image_path in image_path_map.items():
        barcode_record, _ = ArchiveBarcode.objects.update_or_create(
            archive=archive,
            code_type=code_type,
            defaults={
                "code_content": archive.archive_code,
                "image_path": image_path,
                "created_by": operator_id,
            },
        )
        barcode_records.append(barcode_record)

    logger.info("生成档案条码二维码", extra={"archive_id": archive.id, "archive_code": archive.archive_code})
    record_audit_log(
        module_name="ARCHIVES",
        action_code="ARCHIVE_CODE_GENERATE",
        description="生成档案条码和二维码。",
        user=operator,
        biz_type="archive_record",
        biz_id=archive.id,
        target_repr=archive.archive_code,
    )
    return barcode_records


@transaction.atomic
def print_archive_codes(*, archive: ArchiveRecord, operator_id: int) -> list[ArchiveBarcode]:
    barcode_records = list(archive.barcodes.all())
    if not barcode_records:
        raise ValidationError("请先生成档案条码或二维码后再执行打印。")

    operator = _resolve_operator(operator_id)
    printed_at = timezone.now()

    for barcode_record in barcode_records:
        barcode_record.print_count += 1
        barcode_record.last_printed_at = printed_at
        barcode_record.save(update_fields=["print_count", "last_printed_at", "updated_at"])

    logger.info("打印档案条码二维码", extra={"archive_id": archive.id, "archive_code": archive.archive_code})
    record_audit_log(
        module_name="ARCHIVES",
        action_code="ARCHIVE_CODE_PRINT",
        description="发起档案条码和二维码打印，并记录打印留痕。",
        user=operator,
        biz_type="archive_record",
        biz_id=archive.id,
        target_repr=archive.archive_code,
        extra_data={
            "printed_at": printed_at.isoformat(),
            "barcode_ids": [item.id for item in barcode_records],
            "print_count": {item.code_type: item.print_count for item in barcode_records},
        },
    )
    return barcode_records


@transaction.atomic
def batch_print_archive_codes(*, archive_ids: list[int], operator_id: int) -> list[ArchiveRecord]:
    if not archive_ids:
        raise ValidationError("请至少选择一条档案记录。")

    ordered_archive_ids: list[int] = []
    seen_archive_ids: set[int] = set()
    for archive_id in archive_ids:
        if archive_id in seen_archive_ids:
            continue
        seen_archive_ids.add(archive_id)
        ordered_archive_ids.append(archive_id)

    archive_queryset = ArchiveRecord.objects.prefetch_related("barcodes").filter(id__in=ordered_archive_ids)
    archive_map = {archive.id: archive for archive in archive_queryset}

    missing_archive_ids = [str(archive_id) for archive_id in ordered_archive_ids if archive_id not in archive_map]
    if missing_archive_ids:
        raise ValidationError(f"以下档案不存在：{', '.join(missing_archive_ids)}。")

    ordered_archives = [archive_map[archive_id] for archive_id in ordered_archive_ids]
    archives_without_codes = [archive.archive_code for archive in ordered_archives if not archive.barcodes.all()]
    if archives_without_codes:
        raise ValidationError(
            f"以下档案尚未生成条码或二维码：{', '.join(archives_without_codes)}。"
        )

    for archive in ordered_archives:
        print_archive_codes(archive=archive, operator_id=operator_id)

    printed_queryset = (
        ArchiveRecord.objects.select_related("responsible_dept", "location")
        .prefetch_related("barcodes", "revisions", "files")
        .filter(id__in=ordered_archive_ids)
    )
    printed_archive_map = {archive.id: archive for archive in printed_queryset}
    return [printed_archive_map[archive_id] for archive_id in ordered_archive_ids]


def validate_archive_file_access_permission(*, archive_file: ArchiveFile, user) -> None:
    validate_archive_data_scope(archive=archive_file.archive, user=user)
    if archive_file.status != ArchiveFileStatus.ACTIVE:
        raise ValidationError("当前档案文件尚未处理完成，暂不可访问。")
    if not user_can_view_archive_sensitive_fields(user, archive_file.archive):
        raise ValidationError("当前账号无权访问该档案文件。")


def issue_archive_file_preview_ticket_for_user(*, archive_file: ArchiveFile, user, request=None):
    validate_archive_file_access_permission(archive_file=archive_file, user=user)
    expires_at = timezone.now() + timedelta(minutes=int(getattr(settings, "ARCHIVE_FILE_PREVIEW_TICKET_MINUTES", 10)))
    watermark_text = build_watermark_text(user)
    ticket = issue_archive_file_access_ticket(
        archive_file=archive_file,
        user=user,
        access_action=ArchiveFileAccessAction.PREVIEW,
        expires_at=expires_at,
        watermark_text=watermark_text,
    )
    record_audit_log(
        module_name="ARCHIVES",
        action_code="ARCHIVE_FILE_PREVIEW_APPLY",
        description="申请档案文件在线预览票据。",
        user=user,
        biz_type="archive_file",
        biz_id=archive_file.id,
        target_repr=f"{archive_file.archive.archive_code}/{archive_file.file_name}",
        request=request,
        extra_data={"expires_at": expires_at.isoformat()},
    )
    return ticket


def issue_archive_file_download_ticket_for_user(*, archive_file: ArchiveFile, user, purpose: str, request=None):
    validate_archive_file_access_permission(archive_file=archive_file, user=user)
    expires_at = timezone.now() + timedelta(minutes=int(getattr(settings, "ARCHIVE_FILE_DOWNLOAD_TICKET_MINUTES", 5)))
    ticket = issue_archive_file_access_ticket(
        archive_file=archive_file,
        user=user,
        access_action=ArchiveFileAccessAction.DOWNLOAD,
        expires_at=expires_at,
        purpose=purpose,
    )
    record_audit_log(
        module_name="ARCHIVES",
        action_code="ARCHIVE_FILE_DOWNLOAD_APPLY",
        description="申请档案文件下载票据并填写下载用途。",
        user=user,
        biz_type="archive_file",
        biz_id=archive_file.id,
        target_repr=f"{archive_file.archive.archive_code}/{archive_file.file_name}",
        request=request,
        extra_data={"expires_at": expires_at.isoformat(), "purpose": purpose},
    )
    return ticket
