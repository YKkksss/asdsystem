from rest_framework import serializers

from apps.archives.models import ArchiveRecord, ArchiveStorageLocation
from apps.borrowing.models import (
    BorrowApplication,
    BorrowApplicationStatus,
    BorrowApprovalAction,
    BorrowApprovalRecord,
    BorrowCheckoutRecord,
    BorrowReturnAttachment,
    BorrowReturnRecord,
)
from apps.borrowing.services import (
    approve_borrow_application,
    can_user_approve_borrow_application,
    can_user_confirm_borrow_return,
    can_user_submit_borrow_return,
    confirm_borrow_return,
    create_borrow_application,
    register_borrow_checkout,
    submit_borrow_return,
)


class BorrowReturnAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = BorrowReturnAttachment
        fields = [
            "id",
            "attachment_type",
            "file_name",
            "file_path",
            "file_size",
            "uploaded_by",
            "created_at",
        ]
        read_only_fields = fields


class BorrowApprovalRecordSerializer(serializers.ModelSerializer):
    approver_name = serializers.CharField(source="approver.real_name", read_only=True)

    class Meta:
        model = BorrowApprovalRecord
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


class BorrowCheckoutRecordSerializer(serializers.ModelSerializer):
    borrower_name = serializers.CharField(source="borrower.real_name", read_only=True)
    operator_name = serializers.CharField(source="operator.real_name", read_only=True)

    class Meta:
        model = BorrowCheckoutRecord
        fields = [
            "id",
            "application_id",
            "archive_id",
            "borrower_id",
            "borrower_name",
            "operator_id",
            "operator_name",
            "checkout_at",
            "expected_return_at",
            "location_snapshot",
            "checkout_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class BorrowReturnRecordSerializer(serializers.ModelSerializer):
    returned_by_user_name = serializers.CharField(source="returned_by_user.real_name", read_only=True)
    received_by_user_name = serializers.CharField(source="received_by_user.real_name", read_only=True)
    location_after_return_code = serializers.CharField(
        source="location_after_return.full_location_code",
        read_only=True,
    )
    attachments = BorrowReturnAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = BorrowReturnRecord
        fields = [
            "id",
            "application_id",
            "archive_id",
            "returned_by_user_id",
            "returned_by_user_name",
            "received_by_user_id",
            "received_by_user_name",
            "return_status",
            "handover_type",
            "handover_note",
            "returned_at",
            "confirmed_at",
            "location_after_return_id",
            "location_after_return_code",
            "confirm_note",
            "attachments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class BorrowApplicationListSerializer(serializers.ModelSerializer):
    archive_code = serializers.CharField(source="archive.archive_code", read_only=True)
    archive_title = serializers.CharField(source="archive.title", read_only=True)
    archive_status = serializers.CharField(source="archive.status", read_only=True)
    archive_security_level = serializers.CharField(source="archive.security_level", read_only=True)
    applicant_name = serializers.CharField(source="applicant.real_name", read_only=True)
    applicant_dept_name = serializers.CharField(source="applicant_dept.dept_name", read_only=True)
    current_approver_name = serializers.CharField(source="current_approver.real_name", read_only=True)
    return_status = serializers.SerializerMethodField()
    can_approve = serializers.SerializerMethodField()
    can_checkout = serializers.SerializerMethodField()
    can_submit_return = serializers.SerializerMethodField()
    can_confirm_return = serializers.SerializerMethodField()

    def get_can_approve(self, obj: BorrowApplication) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return can_user_approve_borrow_application(user, obj)

    def get_return_status(self, obj: BorrowApplication) -> str | None:
        return_record = getattr(obj, "return_record", None)
        if not return_record:
            return None
        return return_record.return_status

    def get_can_checkout(self, obj: BorrowApplication) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return can_user_confirm_borrow_return(user) and obj.status == BorrowApplicationStatus.APPROVED

    def get_can_submit_return(self, obj: BorrowApplication) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return can_user_submit_borrow_return(user, obj) and obj.status in {
            BorrowApplicationStatus.CHECKED_OUT,
            BorrowApplicationStatus.OVERDUE,
        }

    def get_can_confirm_return(self, obj: BorrowApplication) -> bool:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return can_user_confirm_borrow_return(user) and getattr(obj, "return_record", None) is not None

    class Meta:
        model = BorrowApplication
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
            "purpose",
            "expected_return_at",
            "status",
            "current_approver_id",
            "current_approver_name",
            "submitted_at",
            "approved_at",
            "rejected_at",
            "checkout_at",
            "returned_at",
            "reject_reason",
            "is_overdue",
            "overdue_days",
            "return_status",
            "can_approve",
            "can_checkout",
            "can_submit_return",
            "can_confirm_return",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class BorrowApplicationDetailSerializer(BorrowApplicationListSerializer):
    approval_records = BorrowApprovalRecordSerializer(many=True, read_only=True)
    checkout_record = BorrowCheckoutRecordSerializer(read_only=True)
    return_record = BorrowReturnRecordSerializer(read_only=True)

    class Meta(BorrowApplicationListSerializer.Meta):
        fields = BorrowApplicationListSerializer.Meta.fields + [
            "approval_records",
            "checkout_record",
            "return_record",
        ]
        read_only_fields = fields


class BorrowApplicationWriteSerializer(serializers.Serializer):
    archive_id = serializers.PrimaryKeyRelatedField(queryset=ArchiveRecord.objects.all(), source="archive")
    purpose = serializers.CharField(max_length=500)
    expected_return_at = serializers.DateTimeField()

    def create(self, validated_data: dict) -> BorrowApplication:
        request = self.context["request"]
        return create_borrow_application(
            archive=validated_data["archive"],
            purpose=validated_data["purpose"],
            expected_return_at=validated_data["expected_return_at"],
            operator=request.user,
        )


class BorrowApprovalActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=BorrowApprovalAction.choices)
    opinion = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, attrs: dict) -> dict:
        if attrs["action"] == BorrowApprovalAction.REJECT and not (attrs.get("opinion") or "").strip():
            raise serializers.ValidationError("驳回时必须填写审批意见。")
        return attrs

    def save(self, **kwargs) -> BorrowApplication:
        application = self.context["application"]
        request = self.context["request"]
        return approve_borrow_application(
            application=application,
            approver=request.user,
            action=self.validated_data["action"],
            opinion=(self.validated_data.get("opinion") or "").strip() or None,
        )


class BorrowCheckoutSerializer(serializers.Serializer):
    checkout_note = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def save(self, **kwargs) -> BorrowApplication:
        application = self.context["application"]
        request = self.context["request"]
        return register_borrow_checkout(
            application=application,
            operator=request.user,
            checkout_note=(self.validated_data.get("checkout_note") or "").strip() or None,
        )


class BorrowReturnSubmitSerializer(serializers.Serializer):
    handover_note = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs: dict) -> dict:
        request = self.context["request"]
        photo_files = request.FILES.getlist("photo_files")
        handover_files = request.FILES.getlist("handover_files")
        if not photo_files and not handover_files:
            raise serializers.ValidationError("归还时至少需要上传照片或交接单中的一种。")
        attrs["photo_files"] = photo_files
        attrs["handover_files"] = handover_files
        return attrs

    def save(self, **kwargs) -> BorrowApplication:
        application = self.context["application"]
        request = self.context["request"]
        return submit_borrow_return(
            application=application,
            returned_by=request.user,
            photo_files=self.validated_data["photo_files"],
            handover_files=self.validated_data["handover_files"],
            handover_note=(self.validated_data.get("handover_note") or "").strip() or None,
        )


class BorrowReturnConfirmSerializer(serializers.Serializer):
    approved = serializers.BooleanField()
    location_after_return_id = serializers.PrimaryKeyRelatedField(
        source="location_after_return",
        queryset=ArchiveStorageLocation.objects.filter(status=True),
        required=False,
        allow_null=True,
    )
    confirm_note = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def save(self, **kwargs) -> BorrowApplication:
        application = self.context["application"]
        request = self.context["request"]
        return confirm_borrow_return(
            application=application,
            operator=request.user,
            approved=self.validated_data["approved"],
            confirm_note=(self.validated_data.get("confirm_note") or "").strip() or None,
            location_after_return=self.validated_data.get("location_after_return"),
        )
