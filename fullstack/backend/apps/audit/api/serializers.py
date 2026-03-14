from rest_framework import serializers

from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id",
            "user_id",
            "username",
            "real_name",
            "module_name",
            "action_code",
            "biz_type",
            "biz_id",
            "target_repr",
            "result_status",
            "description",
            "ip_address",
            "user_agent",
            "request_method",
            "request_path",
            "extra_data_json",
            "created_at",
        ]
        read_only_fields = fields

