from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.models import (
    Role,
    SystemPermission,
)
from apps.accounts.services import assign_permissions_to_role, assign_roles_to_user
from apps.organizations.models import Department


User = get_user_model()


class SystemPermissionSerializer(serializers.ModelSerializer):
    parent_id = serializers.PrimaryKeyRelatedField(
        source="parent",
        queryset=SystemPermission.objects.all(),
        required=False,
        allow_null=True,
    )
    parent_name = serializers.CharField(source="parent.permission_name", read_only=True)

    class Meta:
        model = SystemPermission
        fields = [
            "id",
            "parent_id",
            "parent_name",
            "permission_code",
            "permission_name",
            "permission_type",
            "module_name",
            "route_path",
            "sort_order",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_parent_id(self, value: SystemPermission | None) -> SystemPermission | None:
        if value is None or not self.instance:
            return value

        if value.id == self.instance.id:
            raise serializers.ValidationError("上级权限不能选择自己。")

        current_parent = value
        while current_parent:
            if current_parent.id == self.instance.id:
                raise serializers.ValidationError("上级权限不能选择当前权限的下级节点。")
            current_parent = current_parent.parent

        return value


class RoleSerializer(serializers.ModelSerializer):
    permission_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        source="permissions",
        queryset=SystemPermission.objects.filter(status=True),
        required=False,
    )
    permissions = SystemPermissionSerializer(many=True, read_only=True)

    class Meta:
        model = Role
        fields = [
            "id",
            "role_code",
            "role_name",
            "data_scope",
            "status",
            "remark",
            "permission_ids",
            "permissions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "permissions"]

    def create(self, validated_data: dict) -> Role:
        permissions = validated_data.pop("permissions", [])
        role = Role.objects.create(**validated_data)
        assign_permissions_to_role(role, [permission.id for permission in permissions])
        return role

    def update(self, instance: Role, validated_data: dict) -> Role:
        permissions = validated_data.pop("permissions", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if permissions is not None:
            assign_permissions_to_role(instance, [permission.id for permission in permissions])
        return instance


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=6)
    dept_id = serializers.PrimaryKeyRelatedField(
        source="dept",
        queryset=Department.objects.filter(status=True),
    )
    dept_name = serializers.CharField(source="dept.dept_name", read_only=True)
    role_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        source="roles",
        queryset=Role.objects.filter(status=True),
        required=False,
    )
    roles = RoleSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "dept_id",
            "dept_name",
            "username",
            "password",
            "real_name",
            "email",
            "phone",
            "security_clearance_level",
            "status",
            "failed_login_count",
            "last_failed_login_at",
            "lock_until_at",
            "last_login_at",
            "last_login_ip",
            "remark",
            "is_staff",
            "role_ids",
            "roles",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "failed_login_count",
            "last_failed_login_at",
            "lock_until_at",
            "last_login_at",
            "last_login_ip",
            "roles",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data: dict):
        roles = validated_data.pop("roles", [])
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        assign_roles_to_user(user, [role.id for role in roles])
        return user

    def update(self, instance, validated_data: dict):
        roles = validated_data.pop("roles", None)
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        if roles is not None:
            assign_roles_to_user(instance, [role.id for role in roles])
        return instance


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=64)
    password = serializers.CharField(max_length=128)


class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField(max_length=2048)


class UnlockUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
