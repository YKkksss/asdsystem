from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.archives.models import ArchiveFile, ArchiveRecord
from apps.digitization.models import FileProcessJob, ScanTask, ScanTaskItem
from apps.digitization.services import create_scan_task


User = get_user_model()


class ScanAssigneeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    real_name = serializers.CharField()
    dept_id = serializers.IntegerField()


class ArchiveFileSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = ArchiveFile
        fields = [
            "id",
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


class FileProcessJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = FileProcessJob
        fields = [
            "id",
            "job_type",
            "status",
            "retry_count",
            "error_message",
            "started_at",
            "finished_at",
            "created_at",
        ]
        read_only_fields = fields


class ScanTaskItemSerializer(serializers.ModelSerializer):
    archive_code = serializers.CharField(source="archive.archive_code", read_only=True)
    archive_title = serializers.CharField(source="archive.title", read_only=True)
    archive_status = serializers.CharField(source="archive.status", read_only=True)
    files = serializers.SerializerMethodField()

    class Meta:
        model = ScanTaskItem
        fields = [
            "id",
            "archive_id",
            "archive_code",
            "archive_title",
            "archive_status",
            "assignee_user_id",
            "status",
            "uploaded_file_count",
            "last_uploaded_at",
            "error_message",
            "files",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_files(self, obj: ScanTaskItem):
        files = ArchiveFile.objects.filter(scan_task_item_id=obj.id).order_by("sort_order", "id")
        return ArchiveFileSummarySerializer(files, many=True).data


class ScanTaskListSerializer(serializers.ModelSerializer):
    assigned_user_name = serializers.SerializerMethodField()

    class Meta:
        model = ScanTask
        fields = [
            "id",
            "task_no",
            "task_name",
            "assigned_user_id",
            "assigned_user_name",
            "assigned_by",
            "status",
            "total_count",
            "completed_count",
            "failed_count",
            "started_at",
            "finished_at",
            "remark",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_assigned_user_name(self, obj: ScanTask) -> str | None:
        assignee = User.objects.filter(id=obj.assigned_user_id, status=True).only("real_name").first()
        return assignee.real_name if assignee else None


class ScanTaskDetailSerializer(ScanTaskListSerializer):
    items = ScanTaskItemSerializer(many=True, read_only=True)

    class Meta(ScanTaskListSerializer.Meta):
        fields = ScanTaskListSerializer.Meta.fields + ["items"]
        read_only_fields = fields


class ScanTaskWriteSerializer(serializers.Serializer):
    task_name = serializers.CharField(max_length=200)
    assigned_user_id = serializers.IntegerField(required=False, min_value=1)
    archive_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=ArchiveRecord.objects.all(),
        source="archives",
    )
    remark = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate_assigned_user_id(self, value: int) -> int:
        if not User.objects.filter(id=value, status=True, is_staff=True).exists():
            raise serializers.ValidationError("指派执行人不存在或不可用。")
        return value

    def create(self, validated_data: dict) -> ScanTask:
        archives = list(validated_data.pop("archives"))
        assigned_user_id = validated_data.pop("assigned_user_id", None)
        request = self.context["request"]
        return create_scan_task(
            task_name=validated_data["task_name"],
            archives=archives,
            operator_id=request.user.id,
            assigned_user_id=assigned_user_id,
            remark=validated_data.get("remark") or None,
        )
