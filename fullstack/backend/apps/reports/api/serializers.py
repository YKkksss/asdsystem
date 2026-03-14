from rest_framework import serializers

from apps.accounts.models import SecurityClearance
from apps.archives.models import ArchiveStatus
from apps.organizations.models import Department


class ReportFilterSerializer(serializers.Serializer):
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    applicant_dept_id = serializers.PrimaryKeyRelatedField(
        source="applicant_dept",
        queryset=Department.objects.filter(status=True),
        required=False,
        allow_null=True,
    )
    archive_security_level = serializers.ChoiceField(choices=SecurityClearance.choices, required=False)
    archive_status = serializers.ChoiceField(choices=ArchiveStatus.choices, required=False)
    carrier_type = serializers.CharField(required=False, allow_blank=True, max_length=32)

    def validate(self, attrs: dict) -> dict:
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError("开始日期不能晚于结束日期。")
        if "applicant_dept" in attrs:
            attrs["applicant_dept_id"] = attrs["applicant_dept"].id if attrs["applicant_dept"] else None
            attrs.pop("applicant_dept", None)
        if "carrier_type" in attrs:
            attrs["carrier_type"] = (attrs.get("carrier_type") or "").strip() or None
        return attrs


class ReportExportSerializer(ReportFilterSerializer):
    report_type = serializers.ChoiceField(choices=[("departments", "部门借阅统计"), ("archives", "档案利用率统计")])

