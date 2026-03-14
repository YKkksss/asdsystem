from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from django.utils import timezone

from apps.audit.models import AuditResultStatus
from apps.audit.services import record_audit_log
from apps.accounts.api.serializers import (
    LoginSerializer,
    RefreshTokenSerializer,
    RoleSerializer,
    SystemPermissionSerializer,
    UserSerializer,
)
from apps.accounts.models import Role, SystemPermission
from apps.accounts.services import (
    build_user_profile,
    complete_login_success,
    get_locked_until,
    refresh_access_token,
    register_login_failure,
    unlock_user,
)
from apps.common.permissions import IsSystemAdmin
from apps.common.response import error_response, success_response


User = get_user_model()


class RoleViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Role.objects.prefetch_related("permissions").order_by("id")
    serializer_class = RoleSerializer
    permission_classes = [IsSystemAdmin]
    search_fields = ["role_code", "role_name"]
    ordering_fields = ["id", "created_at"]

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.filter_queryset(self.get_queryset()), many=True)
        return success_response(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.save(created_by=request.user.id, updated_by=request.user.id)
        return success_response(
            data=self.get_serializer(role).data,
            message="角色创建成功",
            code=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        role = serializer.save(updated_by=request.user.id)
        return success_response(data=self.get_serializer(role).data, message="角色更新成功")


class SystemPermissionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = SystemPermission.objects.select_related("parent").order_by("sort_order", "id")
    serializer_class = SystemPermissionSerializer
    permission_classes = [IsSystemAdmin]
    search_fields = ["permission_code", "permission_name", "module_name"]
    ordering_fields = ["sort_order", "id", "created_at"]

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.filter_queryset(self.get_queryset()), many=True)
        return success_response(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        permission = serializer.save()
        return success_response(
            data=self.get_serializer(permission).data,
            message="权限创建成功",
            code=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        permission = serializer.save()
        return success_response(data=self.get_serializer(permission).data, message="权限更新成功")


class UserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = User.objects.select_related("dept").prefetch_related(
        Prefetch("roles", queryset=Role.objects.filter(status=True))
    )
    serializer_class = UserSerializer
    permission_classes = [IsSystemAdmin]
    search_fields = ["username", "real_name", "email"]
    ordering_fields = ["id", "created_at", "last_login_at"]

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.filter_queryset(self.get_queryset()), many=True)
        return success_response(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        return success_response(data=self.get_serializer(self.get_object()).data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save(created_by=request.user.id, updated_by=request.user.id)
        return success_response(
            data=self.get_serializer(user).data,
            message="用户创建成功",
            code=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        user = serializer.save(updated_by=request.user.id)
        return success_response(data=self.get_serializer(user).data, message="用户更新成功")


class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        user = User.objects.select_related("dept").filter(username=username).first()
        if not user:
            record_audit_log(
                module_name="AUTH",
                action_code="LOGIN_FAILED",
                description="登录失败，用户名不存在。",
                result_status=AuditResultStatus.FAILED,
                request=request,
                username=username,
                target_repr=username,
            )
            return error_response("用户名或密码错误。", status.HTTP_400_BAD_REQUEST)

        if not user.status:
            return error_response("当前账号已停用，请联系管理员。", status.HTTP_403_FORBIDDEN)

        locked_until = get_locked_until(user)
        if locked_until:
            remaining_seconds = max(int((locked_until - timezone.now()).total_seconds()), 0)
            remaining_minutes = max(1, remaining_seconds // 60)
            record_audit_log(
                module_name="AUTH",
                action_code="LOGIN_LOCKED",
                description="登录被拒绝，账号仍处于锁定期。",
                user=user,
                result_status=AuditResultStatus.DENIED,
                biz_type="system_user",
                biz_id=user.id,
                target_repr=user.username,
                request=request,
                extra_data={"lock_until_at": locked_until.isoformat(), "remaining_seconds": remaining_seconds},
            )
            return error_response(
                f"账号已锁定，请约 {remaining_minutes} 分钟后重试。",
                status.HTTP_423_LOCKED,
                data={"lock_until_at": locked_until.isoformat(), "remaining_seconds": remaining_seconds},
            )

        if not user.check_password(password):
            fail_count, lock_until = register_login_failure(user, request=request)
            if lock_until:
                return error_response(
                    "账号连续输错 3 次，已锁定 15 分钟。",
                    status.HTTP_423_LOCKED,
                    data={"failed_login_count": fail_count, "lock_until_at": lock_until.isoformat()},
                )
            return error_response(
                f"用户名或密码错误，已累计失败 {fail_count} 次。",
                status.HTTP_400_BAD_REQUEST,
                data={"failed_login_count": fail_count},
            )

        tokens = complete_login_success(user, request.META.get("REMOTE_ADDR"), request=request)
        return success_response(
            data={
                "tokens": tokens,
                "profile": build_user_profile(user),
            },
            message="登录成功",
        )


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        record_audit_log(
            module_name="AUTH",
            action_code="LOGOUT",
            description="用户主动退出登录。",
            user=request.user,
            biz_type="system_user",
            biz_id=request.user.id,
            target_repr=request.user.username,
            request=request,
        )
        return success_response(message="退出成功")


class RefreshTokenAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = RefreshTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_data = refresh_access_token(serializer.validated_data["refresh"], request=request)
        return success_response(data=token_data, message="访问令牌刷新成功")


class ProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(data=build_user_profile(request.user))


class UnlockUserAPIView(APIView):
    permission_classes = [IsSystemAdmin]

    def post(self, request, user_id: int):
        user = User.objects.filter(id=user_id).first()
        if not user:
            return error_response("用户不存在。", status.HTTP_404_NOT_FOUND)
        unlock_user(user, operator=request.user, request=request)
        return success_response(message="账号已解锁")
