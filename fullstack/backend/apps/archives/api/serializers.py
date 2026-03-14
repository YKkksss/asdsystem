from rest_framework import serializers

from apps.archives.models import (
    ArchiveBarcode,
    ArchiveFile,
    ArchiveMetadataRevision,
    ArchiveRecord,
    ArchiveStatus,
    ArchiveStorageLocation,
)
from apps.archives.services import (
    MASKED_FILE_TEXT,
    MASKED_RESPONSIBLE_PERSON_TEXT,
    MASKED_SUMMARY_TEXT,
    build_masked_archive_location_detail,
    create_archive_record,
    transition_archive_status,
    update_archive_record,
    user_can_view_archive_sensitive_fields,
)
from apps.organizations.models import Department


class ArchiveStorageLocationSerializer(serializers.ModelSerializer):
    full_location_code = serializers.CharField(read_only=True)

    class Meta:
        model = ArchiveStorageLocation
        fields = [
            "id",
            "warehouse_name",
            "area_name",
            "cabinet_code",
            "rack_code",
            "layer_code",
            "box_code",
            "full_location_code",
            "status",
            "remark",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["full_location_code", "created_by", "updated_by", "created_at", "updated_at"]


class ArchiveBarcodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArchiveBarcode
        fields = [
            "id",
            "code_type",
            "code_content",
            "image_path",
            "print_count",
            "last_printed_at",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class ArchiveMetadataRevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArchiveMetadataRevision
        fields = [
            "id",
            "revision_no",
            "changed_fields_json",
            "snapshot_json",
            "remark",
            "revised_by",
            "revised_at",
        ]
        read_only_fields = fields


class ArchiveFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArchiveFile
        fields = [
            "id",
            "scan_task_item_id",
            "file_name",
            "file_path",
            "thumbnail_path",
            "file_ext",
            "mime_type",
            "file_size",
            "page_count",
            "file_source",
            "sort_order",
            "extracted_text",
            "status",
            "uploaded_by",
            "created_at",
        ]
        read_only_fields = fields


class ArchiveRecordListSerializer(serializers.ModelSerializer):
    responsible_dept_id = serializers.IntegerField(read_only=True)
    responsible_dept_name = serializers.CharField(source="responsible_dept.dept_name", read_only=True)
    location_id = serializers.IntegerField(read_only=True)
    responsible_person = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    location_detail = serializers.SerializerMethodField()
    is_sensitive_masked = serializers.SerializerMethodField()
    masked_fields = serializers.SerializerMethodField()

    def _can_view_sensitive(self, obj: ArchiveRecord) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return user_can_view_archive_sensitive_fields(user, obj)

    def get_responsible_person(self, obj: ArchiveRecord) -> str | None:
        if not obj.responsible_person:
            return None
        if self._can_view_sensitive(obj):
            return obj.responsible_person
        return MASKED_RESPONSIBLE_PERSON_TEXT

    def get_summary(self, obj: ArchiveRecord) -> str | None:
        if not obj.summary:
            return None
        if self._can_view_sensitive(obj):
            return obj.summary
        return MASKED_SUMMARY_TEXT

    def get_location_detail(self, obj: ArchiveRecord) -> dict | None:
        if not obj.location:
            return None
        if self._can_view_sensitive(obj):
            return ArchiveStorageLocationSerializer(obj.location).data
        return build_masked_archive_location_detail(obj.location)

    def get_is_sensitive_masked(self, obj: ArchiveRecord) -> bool:
        return not self._can_view_sensitive(obj)

    def get_masked_fields(self, obj: ArchiveRecord) -> list[str]:
        if self._can_view_sensitive(obj):
            return []
        return ["summary", "responsible_person", "location_detail", "files"]

    class Meta:
        model = ArchiveRecord
        fields = [
            "id",
            "archive_code",
            "title",
            "year",
            "retention_period",
            "security_level",
            "status",
            "responsible_dept_id",
            "responsible_dept_name",
            "responsible_person",
            "formed_at",
            "keywords",
            "summary",
            "page_count",
            "carrier_type",
            "location_id",
            "location_detail",
            "current_borrow_id",
            "catalog_completed_at",
            "shelved_at",
            "is_sensitive_masked",
            "masked_fields",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ArchiveRecordDetailSerializer(ArchiveRecordListSerializer):
    barcodes = ArchiveBarcodeSerializer(many=True, read_only=True)
    revisions = ArchiveMetadataRevisionSerializer(many=True, read_only=True)
    files = serializers.SerializerMethodField()

    def get_files(self, obj: ArchiveRecord) -> list[dict]:
        if self._can_view_sensitive(obj):
            return ArchiveFileSerializer(obj.files.all(), many=True).data
        return [
            {
                "id": 0,
                "scan_task_item_id": None,
                "file_name": MASKED_FILE_TEXT,
                "file_path": "",
                "thumbnail_path": None,
                "file_ext": "",
                "mime_type": None,
                "file_size": 0,
                "page_count": None,
                "file_source": "",
                "sort_order": 0,
                "extracted_text": None,
                "status": "MASKED",
                "uploaded_by": 0,
                "created_at": None,
            }
        ] if obj.files.exists() else []

    class Meta(ArchiveRecordListSerializer.Meta):
        fields = ArchiveRecordListSerializer.Meta.fields + [
            "barcodes",
            "revisions",
            "files",
        ]
        read_only_fields = fields


class ArchiveRecordWriteSerializer(serializers.ModelSerializer):
    responsible_dept_id = serializers.PrimaryKeyRelatedField(
        source="responsible_dept",
        queryset=Department.objects.filter(status=True),
        required=False,
        allow_null=True,
    )
    location_id = serializers.PrimaryKeyRelatedField(
        source="location",
        queryset=ArchiveStorageLocation.objects.filter(status=True),
        required=False,
        allow_null=True,
    )
    revision_remark = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        max_length=255,
    )

    class Meta:
        model = ArchiveRecord
        fields = [
            "id",
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
            "revision_remark",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "current_borrow_id",
            "catalog_completed_at",
            "shelved_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs: dict) -> dict:
        instance = getattr(self, "instance", None)
        year = attrs.get("year", getattr(instance, "year", None))
        formed_at = attrs.get("formed_at", getattr(instance, "formed_at", None))
        if formed_at and year and formed_at.year != year:
            raise serializers.ValidationError("形成日期的年份必须与年度一致。")
        return attrs

    def create(self, validated_data: dict) -> ArchiveRecord:
        revision_remark = validated_data.pop("revision_remark", "")
        operator_id = self.context["request"].user.id
        return create_archive_record(
            validated_data=validated_data,
            operator_id=operator_id,
            revision_remark=revision_remark or None,
        )

    def update(self, instance: ArchiveRecord, validated_data: dict) -> ArchiveRecord:
        revision_remark = validated_data.pop("revision_remark", "")
        operator_id = self.context["request"].user.id
        return update_archive_record(
            archive=instance,
            validated_data=validated_data,
            operator_id=operator_id,
            revision_remark=revision_remark or None,
        )


class ArchiveStatusTransitionSerializer(serializers.Serializer):
    next_status = serializers.ChoiceField(choices=ArchiveStatus.choices)
    current_borrow_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    remark = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def save(self, **kwargs):
        archive = self.context["archive"]
        request = self.context["request"]
        return transition_archive_status(
            archive=archive,
            next_status=self.validated_data["next_status"],
            operator_id=request.user.id,
            remark=self.validated_data.get("remark") or None,
            current_borrow_id=self.validated_data.get("current_borrow_id"),
        )


class ArchiveBatchPrintSerializer(serializers.Serializer):
    archive_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=50,
        error_messages={
            "empty": "请至少选择一条档案记录。",
            "max_length": "单次最多支持打印 50 条档案记录。",
        },
    )

    def validate_archive_ids(self, value: list[int]) -> list[int]:
        ordered_ids: list[int] = []
        seen_ids: set[int] = set()
        for archive_id in value:
            if archive_id in seen_ids:
                continue
            seen_ids.add(archive_id)
            ordered_ids.append(archive_id)
        return ordered_ids


class ArchiveFileDownloadTicketSerializer(serializers.Serializer):
    purpose = serializers.CharField(max_length=255)
