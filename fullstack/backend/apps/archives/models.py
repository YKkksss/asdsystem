from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.accounts.models import SecurityClearance
from apps.common.models import OperatorStampedModel, TimeStampedModel


def build_storage_location_code(
    warehouse_name: str,
    area_name: str | None,
    cabinet_code: str,
    rack_code: str,
    layer_code: str,
    box_code: str,
) -> str:
    return "/".join(
        part
        for part in [
            warehouse_name.strip(),
            (area_name or "").strip(),
            cabinet_code.strip(),
            rack_code.strip(),
            layer_code.strip(),
            box_code.strip(),
        ]
        if part
    )


class ArchiveStatus(models.TextChoices):
    DRAFT = "DRAFT", "草稿"
    PENDING_SCAN = "PENDING_SCAN", "待扫描"
    PENDING_CATALOG = "PENDING_CATALOG", "待编目"
    ON_SHELF = "ON_SHELF", "已上架"
    BORROWED = "BORROWED", "借出中"
    DESTROY_PENDING = "DESTROY_PENDING", "销毁审批中"
    DESTROYED = "DESTROYED", "已销毁"
    FROZEN = "FROZEN", "冻结"


class ArchiveCodeType(models.TextChoices):
    BARCODE = "BARCODE", "条码"
    QRCODE = "QRCODE", "二维码"


class ArchiveFileSource(models.TextChoices):
    SCAN_UPLOAD = "SCAN_UPLOAD", "扫描上传"
    MANUAL_UPLOAD = "MANUAL_UPLOAD", "手工上传"


class ArchiveFileStatus(models.TextChoices):
    PROCESSING = "PROCESSING", "处理中"
    ACTIVE = "ACTIVE", "有效"
    FAILED = "FAILED", "处理失败"


class ArchiveStorageLocation(OperatorStampedModel):
    warehouse_name = models.CharField(max_length=100, db_index=True, verbose_name="库房名称")
    area_name = models.CharField(max_length=100, null=True, blank=True, verbose_name="分区名称")
    cabinet_code = models.CharField(max_length=64, db_index=True, verbose_name="柜号")
    rack_code = models.CharField(max_length=64, verbose_name="架号")
    layer_code = models.CharField(max_length=64, verbose_name="层号")
    box_code = models.CharField(max_length=64, verbose_name="盒号")
    full_location_code = models.CharField(
        max_length=255,
        unique=True,
        verbose_name="完整位置编码",
    )
    status = models.BooleanField(default=True, db_index=True, verbose_name="是否可用")
    remark = models.CharField(max_length=255, null=True, blank=True, verbose_name="备注")

    class Meta:
        db_table = "archive_storage_location"
        ordering = ["warehouse_name", "cabinet_code", "rack_code", "layer_code", "box_code", "id"]
        verbose_name = "实体位置"
        verbose_name_plural = "实体位置"

    def save(self, *args, **kwargs):
        self.full_location_code = build_storage_location_code(
            warehouse_name=self.warehouse_name,
            area_name=self.area_name,
            cabinet_code=self.cabinet_code,
            rack_code=self.rack_code,
            layer_code=self.layer_code,
            box_code=self.box_code,
        )
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.full_location_code


class ArchiveRecord(OperatorStampedModel):
    archive_code = models.CharField(max_length=64, unique=True, verbose_name="档号")
    title = models.CharField(max_length=255, db_index=True, verbose_name="题名")
    year = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1000), MaxValueValidator(9999)],
        db_index=True,
        verbose_name="年度",
    )
    retention_period = models.CharField(max_length=32, db_index=True, verbose_name="保管期限")
    security_level = models.CharField(
        max_length=16,
        choices=SecurityClearance.choices,
        db_index=True,
        verbose_name="密级",
    )
    status = models.CharField(
        max_length=32,
        choices=ArchiveStatus.choices,
        default=ArchiveStatus.DRAFT,
        db_index=True,
        verbose_name="档案状态",
    )
    responsible_dept = models.ForeignKey(
        "organizations.Department",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="archive_records",
        db_column="responsible_dept_id",
        verbose_name="责任部门",
    )
    responsible_person = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        verbose_name="责任人",
    )
    formed_at = models.DateField(null=True, blank=True, verbose_name="形成日期")
    keywords = models.CharField(max_length=500, null=True, blank=True, verbose_name="关键词")
    summary = models.TextField(null=True, blank=True, verbose_name="摘要")
    page_count = models.PositiveIntegerField(null=True, blank=True, verbose_name="页数")
    carrier_type = models.CharField(max_length=32, null=True, blank=True, verbose_name="载体类型")
    location = models.ForeignKey(
        ArchiveStorageLocation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="archive_records",
        db_column="location_id",
        verbose_name="当前实体位置",
    )
    current_borrow_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="当前借阅单 ID",
    )
    catalog_completed_at = models.DateTimeField(null=True, blank=True, verbose_name="编目完成时间")
    shelved_at = models.DateTimeField(null=True, blank=True, verbose_name="上架时间")

    class Meta:
        db_table = "archive_record"
        ordering = ["id"]
        verbose_name = "档案"
        verbose_name_plural = "档案"

    def __str__(self) -> str:
        return f"{self.archive_code} {self.title}"


class ArchiveMetadataRevision(models.Model):
    archive = models.ForeignKey(
        ArchiveRecord,
        on_delete=models.CASCADE,
        related_name="revisions",
        db_column="archive_id",
        verbose_name="档案",
    )
    revision_no = models.PositiveIntegerField(verbose_name="修订版本号")
    changed_fields_json = models.JSONField(verbose_name="变更字段")
    snapshot_json = models.JSONField(verbose_name="完整快照")
    remark = models.CharField(max_length=255, null=True, blank=True, verbose_name="修订说明")
    revised_by = models.PositiveBigIntegerField(db_index=True, verbose_name="修订人")
    revised_at = models.DateTimeField(default=timezone.now, verbose_name="修订时间")

    class Meta:
        db_table = "archive_metadata_revision"
        ordering = ["-revision_no", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["archive", "revision_no"],
                name="uniq_archive_revision_no",
            )
        ]
        verbose_name = "档案修订记录"
        verbose_name_plural = "档案修订记录"


class ArchiveBarcode(TimeStampedModel):
    archive = models.ForeignKey(
        ArchiveRecord,
        on_delete=models.CASCADE,
        related_name="barcodes",
        db_column="archive_id",
        verbose_name="档案",
    )
    code_type = models.CharField(max_length=16, choices=ArchiveCodeType.choices, db_index=True)
    code_content = models.CharField(max_length=255, verbose_name="编码内容")
    image_path = models.CharField(max_length=500, null=True, blank=True, verbose_name="图片路径")
    print_count = models.PositiveIntegerField(default=0, verbose_name="打印次数")
    last_printed_at = models.DateTimeField(null=True, blank=True, verbose_name="最后打印时间")
    created_by = models.PositiveBigIntegerField(null=True, blank=True, verbose_name="创建人")

    class Meta:
        db_table = "archive_barcode"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["archive", "code_type"],
                name="uniq_archive_code_type",
            )
        ]
        verbose_name = "档案条码"
        verbose_name_plural = "档案条码"


class ArchiveFile(models.Model):
    archive = models.ForeignKey(
        ArchiveRecord,
        on_delete=models.CASCADE,
        related_name="files",
        db_column="archive_id",
        verbose_name="档案",
    )
    scan_task_item_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="扫描任务明细 ID",
    )
    file_name = models.CharField(max_length=255, verbose_name="原始文件名")
    file_path = models.CharField(max_length=500, verbose_name="文件路径")
    thumbnail_path = models.CharField(max_length=500, null=True, blank=True, verbose_name="缩略图路径")
    file_ext = models.CharField(max_length=16, db_index=True, verbose_name="文件扩展名")
    mime_type = models.CharField(max_length=64, null=True, blank=True, verbose_name="MIME 类型")
    file_size = models.PositiveBigIntegerField(default=0, verbose_name="文件大小")
    page_count = models.PositiveIntegerField(null=True, blank=True, verbose_name="页数")
    file_source = models.CharField(
        max_length=32,
        choices=ArchiveFileSource.choices,
        default=ArchiveFileSource.SCAN_UPLOAD,
        db_index=True,
        verbose_name="文件来源",
    )
    sort_order = models.IntegerField(default=0, verbose_name="排序值")
    extracted_text = models.TextField(null=True, blank=True, verbose_name="提取文本")
    status = models.CharField(
        max_length=16,
        choices=ArchiveFileStatus.choices,
        default=ArchiveFileStatus.ACTIVE,
        db_index=True,
        verbose_name="文件状态",
    )
    uploaded_by = models.PositiveBigIntegerField(db_index=True, verbose_name="上传人")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")

    class Meta:
        db_table = "archive_file"
        ordering = ["sort_order", "id"]
        verbose_name = "档案文件"
        verbose_name_plural = "档案文件"
