from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import barcode
import qrcode
from barcode.writer import ImageWriter
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from apps.archives.models import (
    ArchiveBarcode,
    ArchiveCodeType,
    ArchiveFile,
    ArchiveFileSource,
    ArchiveFileStatus,
    ArchiveMetadataRevision,
    ArchiveRecord,
    ArchiveStatus,
    ArchiveStorageLocation,
)
from apps.audit.models import AuditLog
from apps.borrowing.models import (
    BorrowApplication,
    BorrowApplicationStatus,
    BorrowApprovalAction,
    BorrowApprovalRecord,
    BorrowCheckoutRecord,
    BorrowReminderChannel,
    BorrowReminderRecord,
    BorrowReminderSendStatus,
    BorrowReminderType,
    BorrowReturnAttachment,
    BorrowReturnAttachmentType,
    BorrowReturnRecord,
    BorrowReturnStatus,
    BorrowHandoverType,
)
from apps.destruction.models import (
    DestroyApplication,
    DestroyApplicationStatus,
    DestroyApprovalAction,
    DestroyApprovalRecord,
    DestroyExecutionAttachment,
    DestroyExecutionRecord,
)
from apps.digitization.models import (
    FileProcessJob,
    FileProcessJobStatus,
    FileProcessJobType,
    ScanTask,
    ScanTaskItem,
    ScanTaskItemStatus,
    ScanTaskStatus,
)
from apps.notifications.models import EmailTask, EmailTaskStatus, NotificationType, SystemNotification
from apps.organizations.models import Department


User = get_user_model()


class Command(BaseCommand):
    help = "初始化演示与验收所需的示例业务数据，可重复执行。"

    def add_arguments(self, parser):
        parser.add_argument("--admin-username", default="admin", help="管理员账号")
        parser.add_argument("--archivist-username", default="archivist", help="档案员账号")
        parser.add_argument("--borrower-username", default="borrower", help="借阅人账号")
        parser.add_argument("--auditor-username", default="auditor", help="审计员账号")

    def _require_user(self, username: str) -> User:
        user = User.objects.filter(username=username).first()
        if not user:
            raise CommandError(
                f"未找到账号 {username}，请先执行 bootstrap_system 初始化基础账号后再创建示例数据。"
            )
        return user

    def _ensure_directory(self, relative_path: str) -> Path:
        directory = Path(settings.MEDIA_ROOT) / relative_path
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def _write_demo_pdf(self, *, relative_path: str, title: str, lines: list[str]) -> int:
        target_path = Path(settings.MEDIA_ROOT) / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        image = Image.new("RGB", (1240, 1754), color="white")
        drawer = ImageDraw.Draw(image)
        drawer.text((72, 72), title, fill=(24, 24, 24))
        current_y = 180
        for line in lines:
            drawer.text((72, current_y), line, fill=(48, 48, 48))
            current_y += 64

        image.save(target_path, "PDF", resolution=150.0)
        return target_path.stat().st_size

    def _write_demo_png(self, *, relative_path: str, title: str, subtitle: str) -> int:
        target_path = Path(settings.MEDIA_ROOT) / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        image = Image.new("RGB", (960, 540), color=(244, 247, 252))
        drawer = ImageDraw.Draw(image)
        drawer.rounded_rectangle((32, 32, 928, 508), radius=28, outline=(40, 93, 181), width=4)
        drawer.text((84, 120), title, fill=(26, 46, 84))
        drawer.text((84, 220), subtitle, fill=(70, 94, 138))
        image.save(target_path, "PNG")
        return target_path.stat().st_size

    def _generate_barcode_image(self, archive: ArchiveRecord) -> str:
        target_dir = self._ensure_directory("barcodes")
        file_base = target_dir / f"archive_{archive.id}_barcode"
        code128 = barcode.get("code128", archive.archive_code, writer=ImageWriter())
        saved_path = Path(code128.save(str(file_base)))
        return saved_path.relative_to(settings.MEDIA_ROOT).as_posix()

    def _generate_qrcode_image(self, archive: ArchiveRecord) -> str:
        target_dir = self._ensure_directory("qrcodes")
        file_path = target_dir / f"archive_{archive.id}_qrcode.png"
        image = qrcode.make(archive.archive_code)
        image.save(file_path)
        return file_path.relative_to(settings.MEDIA_ROOT).as_posix()

    def _ensure_archive_codes(self, archive: ArchiveRecord, operator_id: int) -> None:
        # 直接补齐演示图片文件，避免重复执行命令时产生额外审计日志。
        image_path_map = {
            ArchiveCodeType.BARCODE: self._generate_barcode_image(archive),
            ArchiveCodeType.QRCODE: self._generate_qrcode_image(archive),
        }
        for code_type, image_path in image_path_map.items():
            ArchiveBarcode.objects.update_or_create(
                archive=archive,
                code_type=code_type,
                defaults={
                    "code_content": archive.archive_code,
                    "image_path": image_path,
                    "created_by": operator_id,
                },
            )

    def _ensure_storage_location(
        self,
        *,
        warehouse_name: str,
        area_name: str,
        cabinet_code: str,
        rack_code: str,
        layer_code: str,
        box_code: str,
        remark: str,
        operator_id: int,
    ) -> ArchiveStorageLocation:
        location, _ = ArchiveStorageLocation.objects.get_or_create(
            warehouse_name=warehouse_name,
            area_name=area_name,
            cabinet_code=cabinet_code,
            rack_code=rack_code,
            layer_code=layer_code,
            box_code=box_code,
            defaults={
                "status": True,
                "remark": remark,
                "created_by": operator_id,
                "updated_by": operator_id,
            },
        )
        location.status = True
        location.remark = remark
        location.updated_by = operator_id
        if not location.created_by:
            location.created_by = operator_id
        location.save()
        return location

    def _ensure_archive(
        self,
        *,
        archive_code: str,
        title: str,
        year: int,
        retention_period: str,
        security_level: str,
        status: str,
        responsible_dept: Department,
        responsible_person: str,
        formed_at,
        keywords: str,
        summary: str,
        page_count: int,
        carrier_type: str,
        location: ArchiveStorageLocation | None,
        operator_id: int,
        catalog_completed_at=None,
        shelved_at=None,
    ) -> ArchiveRecord:
        archive, _ = ArchiveRecord.objects.get_or_create(
            archive_code=archive_code,
            defaults={
                "title": title,
                "year": year,
                "retention_period": retention_period,
                "security_level": security_level,
                "status": status,
                "responsible_dept": responsible_dept,
                "responsible_person": responsible_person,
                "formed_at": formed_at,
                "keywords": keywords,
                "summary": summary,
                "page_count": page_count,
                "carrier_type": carrier_type,
                "location": location,
                "catalog_completed_at": catalog_completed_at,
                "shelved_at": shelved_at,
                "created_by": operator_id,
                "updated_by": operator_id,
            },
        )
        archive.title = title
        archive.year = year
        archive.retention_period = retention_period
        archive.security_level = security_level
        archive.status = status
        archive.responsible_dept = responsible_dept
        archive.responsible_person = responsible_person
        archive.formed_at = formed_at
        archive.keywords = keywords
        archive.summary = summary
        archive.page_count = page_count
        archive.carrier_type = carrier_type
        archive.location = location
        archive.catalog_completed_at = catalog_completed_at
        archive.shelved_at = shelved_at
        archive.updated_by = operator_id
        if not archive.created_by:
            archive.created_by = operator_id
        archive.save()
        return archive

    def _ensure_archive_revision(self, *, archive: ArchiveRecord, operator_id: int, remark: str) -> None:
        ArchiveMetadataRevision.objects.update_or_create(
            archive=archive,
            revision_no=1,
            defaults={
                "changed_fields_json": ["archive_code", "title", "status", "security_level"],
                "snapshot_json": {
                    "archive_code": archive.archive_code,
                    "title": archive.title,
                    "status": archive.status,
                    "security_level": archive.security_level,
                    "year": archive.year,
                    "responsible_person": archive.responsible_person,
                },
                "remark": remark,
                "revised_by": operator_id,
                "revised_at": timezone.now(),
            },
        )

    def _ensure_archive_file(
        self,
        *,
        archive: ArchiveRecord,
        file_name: str,
        file_path: str,
        thumbnail_path: str,
        mime_type: str,
        page_count: int,
        extracted_text: str,
        uploaded_by: int,
        scan_task_item_id: int | None = None,
    ) -> ArchiveFile:
        pdf_size = self._write_demo_pdf(
            relative_path=file_path,
            title=f"Archive file {archive.archive_code}",
            lines=[
                f"Archive code: {archive.archive_code}",
                f"Security: {archive.security_level}",
                "Document prepared for deployment demo preview.",
                "This file is generated for deployment demo data.",
            ],
        )
        self._write_demo_png(
            relative_path=thumbnail_path,
            title=archive.archive_code,
            subtitle="Demo thumbnail preview",
        )

        archive_file, _ = ArchiveFile.objects.update_or_create(
            archive=archive,
            file_name=file_name,
            defaults={
                "scan_task_item_id": scan_task_item_id,
                "file_path": file_path,
                "thumbnail_path": thumbnail_path,
                "file_ext": "pdf",
                "mime_type": mime_type,
                "file_size": pdf_size,
                "page_count": page_count,
                "file_source": ArchiveFileSource.SCAN_UPLOAD,
                "sort_order": 1,
                "extracted_text": extracted_text,
                "status": ArchiveFileStatus.ACTIVE,
                "uploaded_by": uploaded_by,
            },
        )
        return archive_file

    def _ensure_file_job(
        self,
        *,
        archive_file: ArchiveFile,
        job_type: str,
        status: str,
        started_at,
        finished_at=None,
        error_message: str | None = None,
    ) -> None:
        FileProcessJob.objects.update_or_create(
            archive_file=archive_file,
            job_type=job_type,
            defaults={
                "status": status,
                "retry_count": 0,
                "error_message": error_message,
                "started_at": started_at,
                "finished_at": finished_at,
            },
        )

    def _ensure_notification(
        self,
        *,
        user: User,
        notification_type: str,
        title: str,
        content: str,
        biz_type: str | None = None,
        biz_id: int | None = None,
        is_read: bool = False,
        read_at=None,
    ) -> SystemNotification:
        notification, _ = SystemNotification.objects.update_or_create(
            user=user,
            title=title,
            defaults={
                "notification_type": notification_type,
                "content": content,
                "biz_type": biz_type,
                "biz_id": biz_id,
                "is_read": is_read,
                "read_at": read_at,
            },
        )
        return notification

    def _ensure_email_task(
        self,
        *,
        receiver_user: User,
        receiver_email: str,
        subject: str,
        content: str,
        biz_type: str | None = None,
        biz_id: int | None = None,
        send_status: str = EmailTaskStatus.SUCCESS,
        scheduled_at=None,
        sent_at=None,
    ) -> EmailTask:
        email_task, _ = EmailTask.objects.update_or_create(
            receiver_email=receiver_email,
            subject=subject,
            defaults={
                "receiver_user": receiver_user,
                "content": content,
                "biz_type": biz_type,
                "biz_id": biz_id,
                "send_status": send_status,
                "scheduled_at": scheduled_at or timezone.now(),
                "sent_at": sent_at,
                "retry_count": 0,
                "error_message": None,
            },
        )
        return email_task

    def _ensure_demo_audit_log(
        self,
        *,
        user: User,
        action_code: str,
        description: str,
        biz_type: str,
        biz_id: int,
        target_repr: str,
    ) -> None:
        exists = AuditLog.objects.filter(
            module_name="DEMO",
            action_code=action_code,
            biz_type=biz_type,
            biz_id=biz_id,
            target_repr=target_repr,
        ).exists()
        if exists:
            return
        AuditLog.objects.create(
            user=user,
            username=user.username,
            real_name=user.real_name,
            module_name="DEMO",
            action_code=action_code,
            biz_type=biz_type,
            biz_id=biz_id,
            target_repr=target_repr,
            description=description,
            extra_data_json={"seed": "bootstrap_demo_data"},
        )

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        today = timezone.localdate()

        admin = self._require_user(options["admin_username"].strip())
        archivist = self._require_user(options["archivist_username"].strip())
        borrower = self._require_user(options["borrower_username"].strip())
        auditor = self._require_user(options["auditor_username"].strip())

        archive_department = Department.objects.filter(dept_code="ARC").first()
        business_department = Department.objects.filter(dept_code="BUS").first()
        audit_department = Department.objects.filter(dept_code="AUD").first()
        if not archive_department or not business_department or not audit_department:
            raise CommandError("未找到默认部门，请先执行 bootstrap_system 初始化基础部门。")

        if not borrower.email:
            borrower.email = "borrower@example.com"
            borrower.save(update_fields=["email", "updated_at"])
        if not archivist.email:
            archivist.email = "archivist@example.com"
            archivist.save(update_fields=["email", "updated_at"])
        if not auditor.email:
            auditor.email = "auditor@example.com"
            auditor.save(update_fields=["email", "updated_at"])

        first_location = self._ensure_storage_location(
            warehouse_name="一号库房",
            area_name="A区",
            cabinet_code="G01",
            rack_code="J01",
            layer_code="L01",
            box_code="H01",
            remark="演示数据默认主库位",
            operator_id=admin.id,
        )
        second_location = self._ensure_storage_location(
            warehouse_name="二号库房",
            area_name="B区",
            cabinet_code="G03",
            rack_code="J02",
            layer_code="L02",
            box_code="H05",
            remark="演示数据备用库位",
            operator_id=admin.id,
        )

        archive_scan_pending = self._ensure_archive(
            archive_code="DEMO-ARC-001",
            title="移交目录补扫卷宗",
            year=2025,
            retention_period="长期",
            security_level="INTERNAL",
            status=ArchiveStatus.PENDING_SCAN,
            responsible_dept=archive_department,
            responsible_person="档案室值守人",
            formed_at=today - timedelta(days=40),
            keywords="移交目录,补扫,待处理",
            summary="用于演示扫描任务进行中的待处理档案。",
            page_count=36,
            carrier_type="纸质",
            location=first_location,
            operator_id=archivist.id,
        )
        archive_on_shelf = self._ensure_archive(
            archive_code="DEMO-ARC-002",
            title="采购合同汇编",
            year=2024,
            retention_period="长期",
            security_level="SECRET",
            status=ArchiveStatus.ON_SHELF,
            responsible_dept=business_department,
            responsible_person="采购专员",
            formed_at=today - timedelta(days=120),
            keywords="采购,合同,供应商",
            summary="包含年度主要采购合同，用于演示检索、脱敏和借阅申请。",
            page_count=64,
            carrier_type="纸质",
            location=first_location,
            operator_id=archivist.id,
            catalog_completed_at=now - timedelta(days=110),
            shelved_at=now - timedelta(days=105),
        )
        archive_borrowed = self._ensure_archive(
            archive_code="DEMO-ARC-003",
            title="项目验收报告",
            year=2024,
            retention_period="长期",
            security_level="CONFIDENTIAL",
            status=ArchiveStatus.BORROWED,
            responsible_dept=business_department,
            responsible_person="项目主管",
            formed_at=today - timedelta(days=160),
            keywords="项目,验收,报告",
            summary="用于演示借阅中与超期催还场景。",
            page_count=42,
            carrier_type="纸质",
            location=second_location,
            operator_id=archivist.id,
            catalog_completed_at=now - timedelta(days=150),
            shelved_at=now - timedelta(days=146),
        )
        archive_returned = self._ensure_archive(
            archive_code="DEMO-ARC-004",
            title="预算执行分析",
            year=2023,
            retention_period="长期",
            security_level="INTERNAL",
            status=ArchiveStatus.ON_SHELF,
            responsible_dept=business_department,
            responsible_person="财务专员",
            formed_at=today - timedelta(days=240),
            keywords="预算,执行,分析",
            summary="用于演示借阅归还、附件与扫描完成场景。",
            page_count=28,
            carrier_type="纸质",
            location=second_location,
            operator_id=archivist.id,
            catalog_completed_at=now - timedelta(days=230),
            shelved_at=now - timedelta(days=226),
        )
        archive_destroy_pending = self._ensure_archive(
            archive_code="DEMO-ARC-005",
            title="人事任免文件",
            year=2022,
            retention_period="10年",
            security_level="CONFIDENTIAL",
            status=ArchiveStatus.DESTROY_PENDING,
            responsible_dept=archive_department,
            responsible_person="人事档案管理员",
            formed_at=today - timedelta(days=420),
            keywords="人事,任免,审批",
            summary="用于演示销毁待审批流程。",
            page_count=18,
            carrier_type="纸质",
            location=first_location,
            operator_id=archivist.id,
            catalog_completed_at=now - timedelta(days=400),
            shelved_at=now - timedelta(days=398),
        )
        archive_destroyed = self._ensure_archive(
            archive_code="DEMO-ARC-006",
            title="历史台账封存卷",
            year=2018,
            retention_period="5年",
            security_level="INTERNAL",
            status=ArchiveStatus.DESTROYED,
            responsible_dept=archive_department,
            responsible_person="历史档案管理员",
            formed_at=today - timedelta(days=820),
            keywords="台账,封存,历史",
            summary="用于演示已执行销毁留痕。",
            page_count=20,
            carrier_type="纸质",
            location=second_location,
            operator_id=archivist.id,
            catalog_completed_at=now - timedelta(days=800),
            shelved_at=now - timedelta(days=792),
        )

        self._ensure_archive_revision(archive=archive_on_shelf, operator_id=archivist.id, remark="初次编目入库")
        self._ensure_archive_revision(archive=archive_returned, operator_id=archivist.id, remark="补充目录信息")

        scan_task_ing = ScanTask.objects.update_or_create(
            task_no="DEMO-SCAN-001",
            defaults={
                "task_name": "历史合同补扫任务",
                "assigned_user_id": archivist.id,
                "assigned_by": admin.id,
                "status": ScanTaskStatus.IN_PROGRESS,
                "total_count": 2,
                "completed_count": 1,
                "failed_count": 0,
                "started_at": now - timedelta(days=1, hours=4),
                "finished_at": None,
                "remark": "演示进行中的数字化任务。",
                "created_by": admin.id,
                "updated_by": archivist.id,
            },
        )[0]
        scan_task_done = ScanTask.objects.update_or_create(
            task_no="DEMO-SCAN-002",
            defaults={
                "task_name": "年度台账整理扫描",
                "assigned_user_id": archivist.id,
                "assigned_by": admin.id,
                "status": ScanTaskStatus.COMPLETED,
                "total_count": 1,
                "completed_count": 1,
                "failed_count": 0,
                "started_at": now - timedelta(days=12),
                "finished_at": now - timedelta(days=11, hours=18),
                "remark": "演示已完成的数字化任务。",
                "created_by": admin.id,
                "updated_by": archivist.id,
            },
        )[0]

        ScanTaskItem.objects.update_or_create(
            task=scan_task_ing,
            archive=archive_scan_pending,
            defaults={
                "assignee_user_id": archivist.id,
                "status": ScanTaskItemStatus.PROCESSING,
                "uploaded_file_count": 0,
                "last_uploaded_at": None,
                "error_message": None,
            },
        )[0]
        scan_item_contract = ScanTaskItem.objects.update_or_create(
            task=scan_task_ing,
            archive=archive_on_shelf,
            defaults={
                "assignee_user_id": archivist.id,
                "status": ScanTaskItemStatus.COMPLETED,
                "uploaded_file_count": 1,
                "last_uploaded_at": now - timedelta(days=1),
                "error_message": None,
            },
        )[0]
        scan_item_budget = ScanTaskItem.objects.update_or_create(
            task=scan_task_done,
            archive=archive_returned,
            defaults={
                "assignee_user_id": archivist.id,
                "status": ScanTaskItemStatus.COMPLETED,
                "uploaded_file_count": 1,
                "last_uploaded_at": now - timedelta(days=11, hours=20),
                "error_message": None,
            },
        )[0]

        contract_file = self._ensure_archive_file(
            archive=archive_on_shelf,
            file_name="DEMO-ARC-002.pdf",
            file_path="demo/archives/DEMO-ARC-002.pdf",
            thumbnail_path="demo/thumbnails/DEMO-ARC-002.png",
            mime_type="application/pdf",
            page_count=3,
            extracted_text="采购合同 合同编号 HT-2024-008 供应商评审与履约条款示例文本。",
            uploaded_by=archivist.id,
            scan_task_item_id=scan_item_contract.id,
        )
        budget_file = self._ensure_archive_file(
            archive=archive_returned,
            file_name="DEMO-ARC-004.pdf",
            file_path="demo/archives/DEMO-ARC-004.pdf",
            thumbnail_path="demo/thumbnails/DEMO-ARC-004.png",
            mime_type="application/pdf",
            page_count=2,
            extracted_text="预算执行分析 成本控制 资金计划 偏差原因说明。",
            uploaded_by=archivist.id,
            scan_task_item_id=scan_item_budget.id,
        )

        self._ensure_file_job(
            archive_file=contract_file,
            job_type=FileProcessJobType.THUMBNAIL,
            status=FileProcessJobStatus.SUCCESS,
            started_at=now - timedelta(days=1, hours=1),
            finished_at=now - timedelta(days=1),
        )
        self._ensure_file_job(
            archive_file=contract_file,
            job_type=FileProcessJobType.TEXT_EXTRACT,
            status=FileProcessJobStatus.SUCCESS,
            started_at=now - timedelta(days=1, hours=1),
            finished_at=now - timedelta(days=1),
        )
        self._ensure_file_job(
            archive_file=budget_file,
            job_type=FileProcessJobType.THUMBNAIL,
            status=FileProcessJobStatus.SUCCESS,
            started_at=now - timedelta(days=11, hours=22),
            finished_at=now - timedelta(days=11, hours=20),
        )
        self._ensure_file_job(
            archive_file=budget_file,
            job_type=FileProcessJobType.TEXT_EXTRACT,
            status=FileProcessJobStatus.SUCCESS,
            started_at=now - timedelta(days=11, hours=22),
            finished_at=now - timedelta(days=11, hours=20),
        )

        for archive in [
            archive_on_shelf,
            archive_borrowed,
            archive_returned,
            archive_destroy_pending,
            archive_destroyed,
        ]:
            self._ensure_archive_codes(archive, archivist.id)

        pending_application = BorrowApplication.objects.update_or_create(
            application_no="DEMO-BORROW-001",
            defaults={
                "archive": archive_on_shelf,
                "applicant": borrower,
                "applicant_dept": business_department,
                "purpose": "用于月度采购复核。",
                "expected_return_at": now + timedelta(days=7),
                "status": BorrowApplicationStatus.PENDING_APPROVAL,
                "current_approver": admin,
                "submitted_at": now - timedelta(days=1, hours=3),
                "approved_at": None,
                "rejected_at": None,
                "withdrawn_at": None,
                "checkout_at": None,
                "returned_at": None,
                "reject_reason": None,
                "is_overdue": False,
                "overdue_days": 0,
                "created_by": borrower.id,
                "updated_by": borrower.id,
            },
        )[0]
        overdue_application = BorrowApplication.objects.update_or_create(
            application_no="DEMO-BORROW-002",
            defaults={
                "archive": archive_borrowed,
                "applicant": borrower,
                "applicant_dept": business_department,
                "purpose": "用于项目复盘与结项核验。",
                "expected_return_at": now - timedelta(days=3),
                "status": BorrowApplicationStatus.OVERDUE,
                "current_approver": None,
                "submitted_at": now - timedelta(days=10),
                "approved_at": now - timedelta(days=9, hours=20),
                "rejected_at": None,
                "withdrawn_at": None,
                "checkout_at": now - timedelta(days=9, hours=18),
                "returned_at": None,
                "reject_reason": None,
                "is_overdue": True,
                "overdue_days": 3,
                "created_by": borrower.id,
                "updated_by": archivist.id,
            },
        )[0]
        returned_application = BorrowApplication.objects.update_or_create(
            application_no="DEMO-BORROW-003",
            defaults={
                "archive": archive_returned,
                "applicant": borrower,
                "applicant_dept": business_department,
                "purpose": "用于预算执行说明会。",
                "expected_return_at": now - timedelta(days=16),
                "status": BorrowApplicationStatus.RETURNED,
                "current_approver": None,
                "submitted_at": now - timedelta(days=20),
                "approved_at": now - timedelta(days=19, hours=12),
                "rejected_at": None,
                "withdrawn_at": None,
                "checkout_at": now - timedelta(days=19),
                "returned_at": now - timedelta(days=17),
                "reject_reason": None,
                "is_overdue": False,
                "overdue_days": 0,
                "created_by": borrower.id,
                "updated_by": archivist.id,
            },
        )[0]

        BorrowApprovalRecord.objects.update_or_create(
            application=overdue_application,
            approver=admin,
            action=BorrowApprovalAction.APPROVE,
            defaults={
                "opinion": "同意借阅，用于项目验收复盘。",
                "approved_at": now - timedelta(days=9, hours=20),
            },
        )
        BorrowApprovalRecord.objects.update_or_create(
            application=returned_application,
            approver=admin,
            action=BorrowApprovalAction.APPROVE,
            defaults={
                "opinion": "同意借阅，用于预算执行分析会。",
                "approved_at": now - timedelta(days=19, hours=12),
            },
        )

        BorrowCheckoutRecord.objects.update_or_create(
            application=overdue_application,
            defaults={
                "archive": archive_borrowed,
                "borrower": borrower,
                "operator": archivist,
                "checkout_at": now - timedelta(days=9, hours=18),
                "expected_return_at": now - timedelta(days=3),
                "location_snapshot": second_location.full_location_code,
                "checkout_note": "已核验身份并完成出库。",
            },
        )
        BorrowCheckoutRecord.objects.update_or_create(
            application=returned_application,
            defaults={
                "archive": archive_returned,
                "borrower": borrower,
                "operator": archivist,
                "checkout_at": now - timedelta(days=19),
                "expected_return_at": now - timedelta(days=16),
                "location_snapshot": second_location.full_location_code,
                "checkout_note": "会后归还。",
            },
        )

        return_record = BorrowReturnRecord.objects.update_or_create(
            application=returned_application,
            defaults={
                "archive": archive_returned,
                "returned_by_user": borrower,
                "received_by_user": archivist,
                "return_status": BorrowReturnStatus.CONFIRMED,
                "handover_type": BorrowHandoverType.BOTH,
                "handover_note": "附带签字交接单与现场照片。",
                "returned_at": now - timedelta(days=17),
                "confirmed_at": now - timedelta(days=16, hours=20),
                "location_after_return": second_location,
                "confirm_note": "档案页码完整，归还后重新上架。",
            },
        )[0]

        return_attachment_size = self._write_demo_png(
            relative_path="demo/borrowing/DEMO-BORROW-003-return.png",
            title="DEMO-BORROW-003",
            subtitle="Return handover photo",
        )
        BorrowReturnAttachment.objects.update_or_create(
            return_record=return_record,
            file_name="DEMO-BORROW-003-return.png",
            defaults={
                "attachment_type": BorrowReturnAttachmentType.PHOTO,
                "file_path": "demo/borrowing/DEMO-BORROW-003-return.png",
                "file_size": return_attachment_size,
                "uploaded_by": borrower.id,
            },
        )

        archive_borrowed.current_borrow_id = overdue_application.id
        archive_borrowed.status = ArchiveStatus.BORROWED
        archive_borrowed.updated_by = archivist.id
        archive_borrowed.save(update_fields=["current_borrow_id", "status", "updated_by", "updated_at"])

        archive_returned.current_borrow_id = None
        archive_returned.status = ArchiveStatus.ON_SHELF
        archive_returned.location = second_location
        archive_returned.updated_by = archivist.id
        archive_returned.save(update_fields=["current_borrow_id", "status", "location", "updated_by", "updated_at"])

        pending_destroy = DestroyApplication.objects.update_or_create(
            application_no="DEMO-DESTROY-001",
            defaults={
                "archive": archive_destroy_pending,
                "applicant": archivist,
                "applicant_dept": archive_department,
                "reason": "保管期限届满且无继续保存价值。",
                "basis": "依据档案保管期限表与清理审批单执行。",
                "status": DestroyApplicationStatus.PENDING_APPROVAL,
                "current_approver": admin,
                "submitted_at": now - timedelta(days=2, hours=4),
                "approved_at": None,
                "rejected_at": None,
                "executed_at": None,
                "reject_reason": None,
                "created_by": archivist.id,
                "updated_by": archivist.id,
            },
        )[0]
        executed_destroy = DestroyApplication.objects.update_or_create(
            application_no="DEMO-DESTROY-002",
            defaults={
                "archive": archive_destroyed,
                "applicant": archivist,
                "applicant_dept": archive_department,
                "reason": "原件保管期届满，已完成复核。",
                "basis": "依据年度销毁审批表第 2026-02 号。",
                "status": DestroyApplicationStatus.EXECUTED,
                "current_approver": None,
                "submitted_at": now - timedelta(days=30),
                "approved_at": now - timedelta(days=26),
                "rejected_at": None,
                "executed_at": now - timedelta(days=24),
                "reject_reason": None,
                "created_by": archivist.id,
                "updated_by": archivist.id,
            },
        )[0]

        DestroyApprovalRecord.objects.update_or_create(
            application=executed_destroy,
            approver=admin,
            action=DestroyApprovalAction.APPROVE,
            defaults={
                "opinion": "同意按流程执行销毁。",
                "approved_at": now - timedelta(days=26),
            },
        )

        destroy_execution_record = DestroyExecutionRecord.objects.update_or_create(
            application=executed_destroy,
            defaults={
                "archive": archive_destroyed,
                "operator": archivist,
                "executed_at": now - timedelta(days=24),
                "execution_note": "已完成纸质粉碎并录入销毁台账。",
                "location_snapshot": second_location.full_location_code,
                "archive_snapshot_json": {
                    "archive_code": archive_destroyed.archive_code,
                    "title": archive_destroyed.title,
                    "status": archive_destroyed.status,
                    "year": archive_destroyed.year,
                },
            },
        )[0]
        destroy_attachment_size = self._write_demo_pdf(
            relative_path="demo/destruction/DEMO-DESTROY-002-proof.pdf",
            title="Destroy proof DEMO-DESTROY-002",
            lines=[
                "Destroy application: DEMO-DESTROY-002",
                "Operator: archivist",
                "Status: executed",
                "This file is generated for demo evidence.",
            ],
        )
        DestroyExecutionAttachment.objects.update_or_create(
            execution_record=destroy_execution_record,
            file_name="DEMO-DESTROY-002-proof.pdf",
            defaults={
                "file_path": "demo/destruction/DEMO-DESTROY-002-proof.pdf",
                "file_size": destroy_attachment_size,
                "uploaded_by": archivist.id,
            },
        )

        self._ensure_notification(
            user=admin,
            notification_type=NotificationType.BORROW_APPROVAL,
            title="示例借阅申请待审批",
            content="DEMO-BORROW-001 等待管理员审批。",
            biz_type="borrow_application",
            biz_id=pending_application.id,
        )
        overdue_site_notification = self._ensure_notification(
            user=borrower,
            notification_type=NotificationType.BORROW_REMINDER,
            title="示例借阅已超期",
            content="DEMO-BORROW-002 已超期 3 天，请尽快归还。",
            biz_type="borrow_application",
            biz_id=overdue_application.id,
        )
        self._ensure_notification(
            user=borrower,
            notification_type=NotificationType.RETURN_CONFIRM,
            title="示例档案归还已确认",
            content="DEMO-BORROW-003 已完成归还验收。",
            biz_type="borrow_application",
            biz_id=returned_application.id,
            is_read=True,
            read_at=now - timedelta(days=16, hours=18),
        )
        self._ensure_notification(
            user=admin,
            notification_type=NotificationType.DESTROY_APPROVAL,
            title="示例销毁申请待审批",
            content="DEMO-DESTROY-001 等待管理员审批。",
            biz_type="destroy_application",
            biz_id=pending_destroy.id,
        )
        self._ensure_notification(
            user=auditor,
            notification_type=NotificationType.SYSTEM,
            title="示例业务数据已初始化",
            content="系统已写入演示档案、借阅、销毁和数字化任务数据。",
            biz_type="system",
            biz_id=0,
        )

        overdue_email_task = self._ensure_email_task(
            receiver_user=borrower,
            receiver_email=borrower.email,
            subject="示例催还提醒：DEMO-BORROW-002",
            content="档案 DEMO-ARC-003 已超期，请尽快归还。",
            biz_type="borrow_application",
            biz_id=overdue_application.id,
            send_status=EmailTaskStatus.SUCCESS,
            scheduled_at=now - timedelta(days=1),
            sent_at=now - timedelta(days=1),
        )

        BorrowReminderRecord.objects.update_or_create(
            application=overdue_application,
            reminder_type=BorrowReminderType.OVERDUE,
            channel=BorrowReminderChannel.SITE,
            defaults={
                "receiver_user": borrower,
                "receiver_email": borrower.email,
                "send_status": BorrowReminderSendStatus.SUCCESS,
                "sent_at": now - timedelta(days=1),
                "content_summary": "借阅超期站内提醒",
                "notification": overdue_site_notification,
                "email_task": None,
            },
        )
        BorrowReminderRecord.objects.update_or_create(
            application=overdue_application,
            reminder_type=BorrowReminderType.OVERDUE,
            channel=BorrowReminderChannel.EMAIL,
            defaults={
                "receiver_user": borrower,
                "receiver_email": borrower.email,
                "send_status": BorrowReminderSendStatus.SUCCESS,
                "sent_at": now - timedelta(days=1),
                "content_summary": "借阅超期邮件提醒",
                "notification": None,
                "email_task": overdue_email_task,
            },
        )

        self._ensure_demo_audit_log(
            user=archivist,
            action_code="DEMO_ARCHIVE_READY",
            description="示例档案与电子文件初始化完成。",
            biz_type="archive_record",
            biz_id=archive_on_shelf.id,
            target_repr=archive_on_shelf.archive_code,
        )
        self._ensure_demo_audit_log(
            user=borrower,
            action_code="DEMO_BORROW_OVERDUE",
            description="示例借阅超期场景已生成。",
            biz_type="borrow_application",
            biz_id=overdue_application.id,
            target_repr=overdue_application.application_no,
        )
        self._ensure_demo_audit_log(
            user=archivist,
            action_code="DEMO_DESTROY_EXECUTED",
            description="示例销毁执行场景已生成。",
            biz_type="destroy_application",
            biz_id=executed_destroy.id,
            target_repr=executed_destroy.application_no,
        )
        self._ensure_demo_audit_log(
            user=auditor,
            action_code="DEMO_SCAN_TASK_READY",
            description="示例数字化任务场景已生成。",
            biz_type="scan_task",
            biz_id=scan_task_ing.id,
            target_repr=scan_task_ing.task_no,
        )

        self.stdout.write(self.style.SUCCESS("示例数据初始化完成。"))
        self.stdout.write(
            self.style.SUCCESS(
                "已准备 2 个实体位置、6 条档案、2 个数字化任务、3 条借阅申请、2 条销毁申请与配套通知。"
            )
        )
