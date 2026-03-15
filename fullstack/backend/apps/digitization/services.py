import logging
import mimetypes
import uuid
from pathlib import Path

import fitz
from PIL import Image
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import record_audit_log
from apps.archives.models import (
    ArchiveFile,
    ArchiveFileSource,
    ArchiveFileStatus,
    ArchiveRecord,
    ArchiveStatus,
)
from apps.archives.services import transition_archive_status
from apps.digitization.models import (
    FileProcessJob,
    FileProcessJobStatus,
    FileProcessJobType,
    ScanTask,
    ScanTaskItem,
    ScanTaskItemStatus,
    ScanTaskStatus,
)
from apps.digitization.tasks import process_file_process_job_task


logger = logging.getLogger(__name__)
User = get_user_model()

ALLOWED_UPLOAD_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "tif", "tiff"}
ARCHIVE_UPLOAD_TRANSITION_STATUSES = {ArchiveStatus.DRAFT, ArchiveStatus.PENDING_SCAN}
INVALID_SCAN_TASK_ARCHIVE_STATUSES = {
    ArchiveStatus.PENDING_CATALOG,
    ArchiveStatus.ON_SHELF,
    ArchiveStatus.BORROWED,
    ArchiveStatus.DESTROY_PENDING,
    ArchiveStatus.DESTROYED,
    ArchiveStatus.FROZEN,
}


def build_scan_task_no() -> str:
    return f"SCAN{timezone.now():%Y%m%d%H%M%S}{uuid.uuid4().hex[:6].upper()}"


def _resolve_operator(operator_id: int | None):
    if not operator_id:
        return None
    return User.objects.filter(id=operator_id, status=True).first()


def validate_scan_task_archives(archives: list[ArchiveRecord]) -> None:
    if not archives:
        raise ValidationError("扫描任务至少需要选择一份档案。")

    invalid_archives = [archive.archive_code for archive in archives if archive.status in INVALID_SCAN_TASK_ARCHIVE_STATUSES]
    if invalid_archives:
        raise ValidationError(f"以下档案当前状态不允许创建扫描任务：{', '.join(invalid_archives)}。")

    duplicated_archives = list(
        ScanTaskItem.objects.filter(
            archive_id__in=[archive.id for archive in archives],
            task__status__in=[ScanTaskStatus.PENDING, ScanTaskStatus.IN_PROGRESS],
        )
        .values_list("archive__archive_code", flat=True)
        .distinct()
    )
    if duplicated_archives:
        raise ValidationError(f"以下档案已存在未完成扫描任务：{', '.join(duplicated_archives)}。")


def sync_scan_task_counters(task: ScanTask) -> ScanTask:
    counts = task.items.aggregate(
        total_count=Count("id"),
        completed_count=Count("id", filter=Q(status=ScanTaskItemStatus.COMPLETED)),
        failed_count=Count("id", filter=Q(status=ScanTaskItemStatus.FAILED)),
        processing_count=Count("id", filter=Q(status=ScanTaskItemStatus.PROCESSING)),
    )
    task.total_count = counts["total_count"] or 0
    task.completed_count = counts["completed_count"] or 0
    task.failed_count = counts["failed_count"] or 0

    processing_count = counts["processing_count"] or 0
    if task.total_count == 0:
        task.status = ScanTaskStatus.PENDING
        task.started_at = None
        task.finished_at = None
    elif task.completed_count + task.failed_count == task.total_count:
        task.status = ScanTaskStatus.FAILED if task.failed_count else ScanTaskStatus.COMPLETED
        task.started_at = task.started_at or timezone.now()
        task.finished_at = timezone.now()
    elif processing_count or task.completed_count or task.failed_count:
        task.status = ScanTaskStatus.IN_PROGRESS
        task.started_at = task.started_at or timezone.now()
        task.finished_at = None
    else:
        task.status = ScanTaskStatus.PENDING
        task.finished_at = None

    task.save(
        update_fields=[
            "total_count",
            "completed_count",
            "failed_count",
            "status",
            "started_at",
            "finished_at",
            "updated_at",
        ]
    )
    return task


@transaction.atomic
def create_scan_task(
    *,
    task_name: str,
    archives: list[ArchiveRecord],
    operator_id: int,
    assigned_user_id: int | None = None,
    remark: str | None = None,
) -> ScanTask:
    operator = _resolve_operator(operator_id)
    validate_scan_task_archives(archives)

    assigned_user_id = assigned_user_id or operator_id
    task = ScanTask.objects.create(
        task_no=build_scan_task_no(),
        task_name=task_name,
        assigned_user_id=assigned_user_id,
        assigned_by=operator_id,
        remark=remark,
        created_by=operator_id,
        updated_by=operator_id,
    )

    scan_task_items = [
        ScanTaskItem(
            task=task,
            archive=archive,
            assignee_user_id=assigned_user_id,
        )
        for archive in archives
    ]
    ScanTaskItem.objects.bulk_create(scan_task_items)

    for archive in archives:
        if archive.status == ArchiveStatus.DRAFT:
            transition_archive_status(
                archive=archive,
                next_status=ArchiveStatus.PENDING_SCAN,
                operator_id=operator_id,
                remark=f"创建扫描任务：{task.task_no}",
            )

    sync_scan_task_counters(task)
    record_audit_log(
        module_name="DIGITIZATION",
        action_code="SCAN_TASK_CREATE",
        description="创建扫描任务并绑定档案列表。",
        user=operator,
        biz_type="scan_task",
        biz_id=task.id,
        target_repr=task.task_no,
        extra_data={"archive_ids": [archive.id for archive in archives], "assigned_user_id": assigned_user_id},
    )
    logger.info("创建扫描任务", extra={"task_id": task.id, "task_no": task.task_no})
    return task


def validate_uploaded_file(uploaded_file) -> str:
    file_name = Path(uploaded_file.name).name
    extension = Path(file_name).suffix.lower().lstrip(".")
    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValidationError(f"不支持的文件格式：{extension or '未知'}。")

    max_size = settings.ARCHIVE_UPLOAD_MAX_SIZE_MB * 1024 * 1024
    if uploaded_file.size > max_size:
        raise ValidationError(f"单个文件大小不能超过 {settings.ARCHIVE_UPLOAD_MAX_SIZE_MB} MB。")

    return extension


def _build_relative_upload_path(task_item: ScanTaskItem, original_name: str) -> str:
    extension = Path(original_name).suffix.lower()
    stored_name = f"{timezone.now():%Y%m%d%H%M%S}_{uuid.uuid4().hex[:8]}{extension}"
    relative_path = (
        Path("archive-files")
        / timezone.now().strftime("%Y%m")
        / f"task_{task_item.task_id}"
        / f"archive_{task_item.archive_id}"
        / stored_name
    )
    return relative_path.as_posix()


def _build_relative_derived_path(prefix: str, archive_file: ArchiveFile, suffix: str = ".png") -> str:
    relative_path = (
        Path(prefix)
        / timezone.now().strftime("%Y%m")
        / f"archive_{archive_file.archive_id}"
        / f"file_{archive_file.id}{suffix}"
    )
    return relative_path.as_posix()


def _absolute_media_path(relative_path: str) -> Path:
    return Path(settings.MEDIA_ROOT) / relative_path


def _ensure_parent_directory(relative_path: str) -> None:
    _absolute_media_path(relative_path).parent.mkdir(parents=True, exist_ok=True)


def _finalize_archive_file_status(archive_file: ArchiveFile) -> ArchiveFile:
    failed_exists = archive_file.process_jobs.filter(status=FileProcessJobStatus.FAILED).exists()
    pending_exists = archive_file.process_jobs.filter(
        status__in=[FileProcessJobStatus.PENDING, FileProcessJobStatus.PROCESSING]
    ).exists()
    if failed_exists:
        archive_file.status = ArchiveFileStatus.FAILED
    elif pending_exists:
        archive_file.status = ArchiveFileStatus.PROCESSING
    else:
        archive_file.status = ArchiveFileStatus.ACTIVE
    archive_file.save(update_fields=["status"])
    return archive_file


def sync_scan_task_item_status(task_item_id: int) -> ScanTaskItem | None:
    task_item = ScanTaskItem.objects.select_related("task").filter(id=task_item_id).first()
    if not task_item:
        return None

    files = ArchiveFile.objects.filter(scan_task_item_id=task_item.id)
    file_count = files.count()
    latest_uploaded_at = files.order_by("-created_at").values_list("created_at", flat=True).first()

    next_status = ScanTaskItemStatus.PENDING
    next_error_message = None

    if file_count > 0:
        if files.filter(status=ArchiveFileStatus.FAILED).exists():
            next_status = ScanTaskItemStatus.FAILED
            latest_failed_job = (
                FileProcessJob.objects.filter(
                    archive_file__scan_task_item_id=task_item.id,
                    status=FileProcessJobStatus.FAILED,
                )
                .order_by("-id")
                .first()
            )
            next_error_message = (
                latest_failed_job.error_message if latest_failed_job and latest_failed_job.error_message else "文件处理失败。"
            )
        elif files.filter(status=ArchiveFileStatus.PROCESSING).exists():
            next_status = ScanTaskItemStatus.PROCESSING
        else:
            next_status = ScanTaskItemStatus.COMPLETED

    update_fields: list[str] = []
    if task_item.status != next_status:
        task_item.status = next_status
        update_fields.append("status")

    if task_item.uploaded_file_count != file_count:
        task_item.uploaded_file_count = file_count
        update_fields.append("uploaded_file_count")

    if task_item.last_uploaded_at != latest_uploaded_at:
        task_item.last_uploaded_at = latest_uploaded_at
        update_fields.append("last_uploaded_at")

    if task_item.error_message != next_error_message:
        task_item.error_message = next_error_message
        update_fields.append("error_message")

    if update_fields:
        task_item.save(update_fields=update_fields + ["updated_at"])

    sync_scan_task_counters(task_item.task)
    return task_item


def process_file_process_job(job_id: int) -> None:
    job = FileProcessJob.objects.select_related("archive_file").filter(id=job_id).first()
    if not job:
        return

    archive_file = job.archive_file
    absolute_file_path = _absolute_media_path(archive_file.file_path)
    job.status = FileProcessJobStatus.PROCESSING
    job.started_at = timezone.now()
    job.error_message = None
    job.save(update_fields=["status", "started_at", "error_message"])

    try:
        if job.job_type == FileProcessJobType.THUMBNAIL:
            if archive_file.file_ext == "pdf":
                document = fitz.open(absolute_file_path)
                archive_file.page_count = document.page_count
                first_page = document.load_page(0)
                pix = first_page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                relative_thumbnail_path = _build_relative_derived_path("thumbnails", archive_file)
                _ensure_parent_directory(relative_thumbnail_path)
                pix.save(_absolute_media_path(relative_thumbnail_path))
                archive_file.thumbnail_path = relative_thumbnail_path
                archive_file.save(update_fields=["page_count", "thumbnail_path"])
                document.close()
            else:
                relative_thumbnail_path = _build_relative_derived_path("thumbnails", archive_file)
                _ensure_parent_directory(relative_thumbnail_path)
                with Image.open(absolute_file_path) as image:
                    image.thumbnail((480, 480))
                    image.convert("RGB").save(_absolute_media_path(relative_thumbnail_path), format="PNG")
                archive_file.thumbnail_path = relative_thumbnail_path
                archive_file.page_count = 1
                archive_file.save(update_fields=["thumbnail_path", "page_count"])
        elif job.job_type == FileProcessJobType.TEXT_EXTRACT:
            extracted_text = ""
            if archive_file.file_ext == "pdf":
                document = fitz.open(absolute_file_path)
                extracted_text = "\n".join(page.get_text("text") for page in document)
                archive_file.page_count = archive_file.page_count or document.page_count
                document.close()
            archive_file.extracted_text = extracted_text.strip() or None
            archive_file.save(update_fields=["extracted_text", "page_count"])

        job.status = FileProcessJobStatus.SUCCESS
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "finished_at"])
    except Exception as exc:
        job.status = FileProcessJobStatus.FAILED
        job.retry_count += 1
        job.error_message = str(exc)
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "retry_count", "error_message", "finished_at"])
        logger.exception("处理文件任务失败", extra={"job_id": job.id, "archive_file_id": archive_file.id})
    finally:
        _finalize_archive_file_status(archive_file)
        if archive_file.scan_task_item_id:
            sync_scan_task_item_status(archive_file.scan_task_item_id)


def dispatch_file_process_job(job: FileProcessJob) -> None:
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        process_file_process_job(job.id)
        return

    try:
        process_file_process_job_task.delay(job.id)
    except Exception:
        logger.warning("Celery 不可用，回退为同步处理", extra={"job_id": job.id})
        process_file_process_job(job.id)


def dispatch_file_process_jobs_after_commit(job_ids: list[int]) -> None:
    # 仅在事务真正提交后再派发任务，避免 Worker 读取到尚未提交的任务记录。
    def _dispatch() -> None:
        jobs = FileProcessJob.objects.filter(id__in=job_ids).order_by("id")
        for job in jobs:
            dispatch_file_process_job(job)

    transaction.on_commit(_dispatch)


@transaction.atomic
def upload_files_to_scan_task_item(
    *,
    task_item: ScanTaskItem,
    uploaded_files: list,
    operator_id: int,
) -> ScanTaskItem:
    operator = _resolve_operator(operator_id)
    if not uploaded_files:
        raise ValidationError("至少需要上传一个文件。")

    task_item.status = ScanTaskItemStatus.PROCESSING
    task_item.error_message = None
    task_item.save(update_fields=["status", "error_message", "updated_at"])

    try:
        current_max_sort_order = (
            ArchiveFile.objects.filter(archive=task_item.archive).aggregate(max_sort_order=Max("sort_order"))[
                "max_sort_order"
            ]
            or 0
        )

        for index, uploaded_file in enumerate(uploaded_files, start=1):
            file_ext = validate_uploaded_file(uploaded_file)
            relative_path = _build_relative_upload_path(task_item, uploaded_file.name)
            _ensure_parent_directory(relative_path)
            saved_path = default_storage.save(relative_path, uploaded_file)
            mime_type = uploaded_file.content_type or mimetypes.guess_type(uploaded_file.name)[0]

            archive_file = ArchiveFile.objects.create(
                archive=task_item.archive,
                scan_task_item_id=task_item.id,
                file_name=Path(uploaded_file.name).name,
                file_path=saved_path,
                file_ext=file_ext,
                mime_type=mime_type,
                file_size=uploaded_file.size,
                file_source=ArchiveFileSource.SCAN_UPLOAD,
                sort_order=current_max_sort_order + index,
                status=ArchiveFileStatus.PROCESSING,
                uploaded_by=operator_id,
            )

            jobs = [
                FileProcessJob.objects.create(
                    archive_file=archive_file,
                    job_type=FileProcessJobType.THUMBNAIL,
                )
            ]
            if file_ext == "pdf":
                jobs.append(
                    FileProcessJob.objects.create(
                        archive_file=archive_file,
                        job_type=FileProcessJobType.TEXT_EXTRACT,
                    )
                )

            dispatch_file_process_jobs_after_commit([job.id for job in jobs])

        task_item.uploaded_file_count += len(uploaded_files)
        task_item.last_uploaded_at = timezone.now()
        task_item.status = ScanTaskItemStatus.PROCESSING
        task_item.error_message = None
        task_item.save(
            update_fields=["uploaded_file_count", "last_uploaded_at", "status", "error_message", "updated_at"]
        )

        if task_item.archive.status in ARCHIVE_UPLOAD_TRANSITION_STATUSES:
            transition_archive_status(
                archive=task_item.archive,
                next_status=ArchiveStatus.PENDING_CATALOG,
                operator_id=operator_id,
                remark=f"扫描文件上传完成：任务 {task_item.task.task_no}",
            )

        sync_scan_task_counters(task_item.task)
        record_audit_log(
            module_name="DIGITIZATION",
            action_code="SCAN_TASK_FILE_UPLOAD",
            description="上传扫描文件并触发缩略图与文本提取处理。",
            user=operator,
            biz_type="scan_task_item",
            biz_id=task_item.id,
            target_repr=task_item.task.task_no,
            extra_data={"archive_id": task_item.archive_id, "file_count": len(uploaded_files)},
        )
        logger.info(
            "扫描任务上传文件成功",
            extra={"task_id": task_item.task_id, "task_item_id": task_item.id, "archive_id": task_item.archive_id},
        )
    except ValidationError:
        task_item.status = ScanTaskItemStatus.FAILED
        task_item.save(update_fields=["status", "updated_at"])
        sync_scan_task_counters(task_item.task)
        raise
    except Exception as exc:
        task_item.status = ScanTaskItemStatus.FAILED
        task_item.error_message = str(exc)
        task_item.save(update_fields=["status", "error_message", "updated_at"])
        logger.exception("扫描任务上传失败", extra={"task_item_id": task_item.id})
        sync_scan_task_counters(task_item.task)
        raise ValidationError("文件上传处理失败，请稍后重试。")
    return task_item
