from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.organizations.models import Department
from apps.organizations.services import sync_department_hierarchy


User = get_user_model()


class DepartmentSerializer(serializers.ModelSerializer):
    parent_id = serializers.PrimaryKeyRelatedField(
        source="parent",
        queryset=Department.objects.all(),
        required=False,
        allow_null=True,
    )
    parent_name = serializers.CharField(source="parent.dept_name", read_only=True)
    approver_user_name = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = [
            "id",
            "parent_id",
            "parent_name",
            "dept_code",
            "dept_name",
            "dept_path",
            "dept_level",
            "sort_order",
            "approver_user_id",
            "approver_user_name",
            "status",
            "remark",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["dept_path", "dept_level", "created_at", "updated_at"]

    def get_approver_user_name(self, obj: Department) -> str | None:
        if not obj.approver_user_id:
            return None
        approver = User.objects.filter(id=obj.approver_user_id).only("real_name").first()
        return approver.real_name if approver else None

    def validate_approver_user_id(self, value: int | None) -> int | None:
        if value is None:
            return value
        if not User.objects.filter(id=value, status=True).exists():
            raise serializers.ValidationError("审批负责人不存在或已停用。")
        return value

    def validate(self, attrs: dict) -> dict:
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        if self.instance and parent and parent.id == self.instance.id:
            raise serializers.ValidationError({"parent_id": "上级部门不能选择自己。"})

        if self.instance and parent and parent.dept_path.startswith(f"{self.instance.dept_path}/"):
            raise serializers.ValidationError({"parent_id": "上级部门不能选择当前部门的子部门。"})

        return attrs

    def create(self, validated_data: dict) -> Department:
        department = Department.objects.create(**validated_data)
        return sync_department_hierarchy(department)

    def update(self, instance: Department, validated_data: dict) -> Department:
        parent = validated_data.pop("parent", instance.parent)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.parent = parent
        instance.save()
        return sync_department_hierarchy(instance)
