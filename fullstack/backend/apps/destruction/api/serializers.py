from rest_framework import serializers

from apps.archives.models import ArchiveRecord
from apps.destruction.models import (
    DestroyApplication,
    DestroyApprovalAction,
    DestroyApprovalRecord,
    DestroyExecutionAttachment,
    DestroyExecutionRecord,
)
from apps.destruction.services import (
    approve_destroy_application,
    can_user_approve_destroy_application,
    can_user_execute_destroy_application,
    create_destroy_application,
    execute_destroy_application,
)


class DestroyExecutionAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DestroyExecutionAttachment
        fields = [
            "id",
            "file_name",
            "file_path",
            "file_size",
            "uploaded_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class DestroyApprovalRecordSerializer(serializers.ModelSerializer):
    approver_name = serializers.CharField(source="approver.real_name", read_only=True)

    class Meta:
        model = DestroyApprovalRecord
        fields = [
            "id",
            "approver_id",
            "approver_name",
            "action",
            "opinion",
            "approved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class DestroyExecutionRecordSerializer(serializers.ModelSerializer):
    operator_name = serializers.CharField(source="operator.real_name", read_only=True)
    attachments = DestroyExecutionAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = DestroyExecutionRecord
        fields = [
            "id",
            "application_id",
            "archive_id",
            "operator_id",
            "operator_name",
            "executed_at",
            "execution_note",
            "location_snapshot",
            "archive_snapshot_json",
            "attachments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class DestroyApplicationListSerializer(serializers.ModelSerializer):
    archive_code = serializers.CharField(source="archive.archive_code", read_only=True)
    archive_title = serializers.CharField(source="archive.title", read_only=True)
    archive_status = serializers.CharField(source="archive.status", read_only=True)
    archive_security_level = serializers.CharField(source="archive.security_level", read_only=True)
    applicant_name = serializers.CharField(source="applicant.real_name", read_only=True)
    applicant_dept_name = serializers.CharField(source="applicant_dept.dept_name", read_only=True)
    current_approver_name = serializers.CharField(source="current_approver.real_name", read_only=True)
    can_approve = serializers.SerializerMethodField()
    can_execute = serializers.SerializerMethodField()

    def get_can_approve(self, obj: DestroyApplication) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return can_user_approve_destroy_application(user, obj)

    def get_can_execute(self, obj: DestroyApplication) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return can_user_execute_destroy_application(user, obj)

    class Meta:
        model = DestroyApplication
        fields = [
            "id",
            "application_no",
            "archive_id",
            "archive_code",
            "archive_title",
            "archive_status",
            "archive_security_level",
            "applicant_id",
            "applicant_name",
            "applicant_dept_id",
            "applicant_dept_name",
            "reason",
            "basis",
            "status",
            "current_approver_id",
            "current_approver_name",
            "submitted_at",
            "approved_at",
            "rejected_at",
            "executed_at",
            "reject_reason",
            "can_approve",
            "can_execute",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class DestroyApplicationDetailSerializer(DestroyApplicationListSerializer):
    approval_records = DestroyApprovalRecordSerializer(many=True, read_only=True)
    execution_record = DestroyExecutionRecordSerializer(read_only=True)

    class Meta(DestroyApplicationListSerializer.Meta):
        fields = DestroyApplicationListSerializer.Meta.fields + [
            "approval_records",
            "execution_record",
        ]
        read_only_fields = fields


class DestroyApplicationWriteSerializer(serializers.Serializer):
    archive_id = serializers.PrimaryKeyRelatedField(queryset=ArchiveRecord.objects.all(), source="archive")
    reason = serializers.CharField(max_length=500)
    basis = serializers.CharField(max_length=500)

    def create(self, validated_data: dict) -> DestroyApplication:
        request = self.context["request"]
        return create_destroy_application(
            archive=validated_data["archive"],
            reason=validated_data["reason"],
            basis=validated_data["basis"],
            operator=request.user,
        )


class DestroyApprovalActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=DestroyApprovalAction.choices)
    opinion = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, attrs: dict) -> dict:
        if attrs["action"] == DestroyApprovalAction.REJECT and not (attrs.get("opinion") or "").strip():
            raise serializers.ValidationError("驳回时必须填写审批意见。")
        return attrs

    def save(self, **kwargs) -> DestroyApplication:
        application = self.context["application"]
        request = self.context["request"]
        return approve_destroy_application(
            application=application,
            approver=request.user,
            action=self.validated_data["action"],
            opinion=(self.validated_data.get("opinion") or "").strip() or None,
        )


class DestroyExecutionSerializer(serializers.Serializer):
    execution_note = serializers.CharField(max_length=500)

    def validate(self, attrs: dict) -> dict:
        request = self.context["request"]
        attrs["attachment_files"] = request.FILES.getlist("attachment_files")
        return attrs

    def save(self, **kwargs) -> DestroyApplication:
        application = self.context["application"]
        request = self.context["request"]
        return execute_destroy_application(
            application=application,
            operator=request.user,
            execution_note=self.validated_data["execution_note"].strip(),
            attachment_files=self.validated_data["attachment_files"],
        )

