from django.db.models import Q
from rest_framework import decorators, mixins, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser

from apps.common.permissions import HasConfiguredSystemPermission
from apps.common.pagination import OptionalPaginationListMixin
from apps.common.response import success_response
from apps.destruction.api.serializers import (
    DestroyApplicationDetailSerializer,
    DestroyApplicationListSerializer,
    DestroyApplicationWriteSerializer,
    DestroyApprovalActionSerializer,
    DestroyExecutionSerializer,
)
from apps.destruction.models import DestroyApplication, DestroyApplicationStatus
from apps.destruction.services import is_admin_or_auditor_user, is_archive_manager_user

DESTROY_READ_PERMISSION_CODES = {"menu.destruction_center"}
DESTROY_CREATE_PERMISSION_CODES = {"button.destruction.create"}
DESTROY_APPROVE_PERMISSION_CODES = {"button.destruction.approve"}
DESTROY_EXECUTE_PERMISSION_CODES = {"button.destruction.execute"}
DESTROY_READ_FALLBACK_ROLES = {"ADMIN", "ARCHIVIST"}
DESTROY_ARCHIVE_MANAGER_FALLBACK_ROLES = {"ADMIN", "ARCHIVIST"}
DESTROY_APPROVE_FALLBACK_ROLES = {"ADMIN"}


class DestroyApplicationViewSet(
    OptionalPaginationListMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = DestroyApplication.objects.select_related(
        "archive",
        "applicant",
        "applicant_dept",
        "current_approver",
    ).order_by("-id")
    search_fields = ["application_no", "reason", "basis", "archive__archive_code", "archive__title", "applicant__real_name"]
    ordering_fields = ["id", "created_at", "submitted_at", "approved_at", "executed_at"]
    filterset_fields = ["status", "archive_id", "applicant_id", "applicant_dept_id", "current_approver_id"]
    permission_classes = [HasConfiguredSystemPermission]
    action_required_permission_codes = {
        "list": DESTROY_READ_PERMISSION_CODES,
        "retrieve": DESTROY_READ_PERMISSION_CODES,
        "create": DESTROY_CREATE_PERMISSION_CODES,
        "approve": DESTROY_APPROVE_PERMISSION_CODES,
        "execute": DESTROY_EXECUTE_PERMISSION_CODES,
    }
    action_permission_fallback_roles = {
        "list": DESTROY_READ_FALLBACK_ROLES,
        "retrieve": DESTROY_READ_FALLBACK_ROLES,
        "create": DESTROY_ARCHIVE_MANAGER_FALLBACK_ROLES,
        "approve": DESTROY_APPROVE_FALLBACK_ROLES,
        "execute": DESTROY_ARCHIVE_MANAGER_FALLBACK_ROLES,
    }

    def get_serializer_class(self):
        if self.action == "create":
            return DestroyApplicationWriteSerializer
        if self.action == "retrieve":
            return DestroyApplicationDetailSerializer
        return DestroyApplicationListSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params
        user = self.request.user

        scope = (params.get("scope") or "").strip().lower()
        if scope == "mine":
            queryset = queryset.filter(applicant_id=user.id)
        elif scope == "approval":
            if not is_admin_or_auditor_user(user):
                queryset = queryset.none()
            else:
                queryset = queryset.filter(
                    status=DestroyApplicationStatus.PENDING_APPROVAL,
                    current_approver_id=user.id,
                )
        elif scope == "execution":
            if not is_archive_manager_user(user):
                queryset = queryset.none()
            else:
                queryset = queryset.filter(status=DestroyApplicationStatus.APPROVED)
        elif scope == "all":
            if not (is_archive_manager_user(user) or is_admin_or_auditor_user(user)):
                queryset = queryset.filter(Q(applicant_id=user.id) | Q(current_approver_id=user.id))
        else:
            if not (is_archive_manager_user(user) or is_admin_or_auditor_user(user)):
                queryset = queryset.filter(Q(applicant_id=user.id) | Q(current_approver_id=user.id))

        keyword = (params.get("keyword") or "").strip()
        if keyword:
            queryset = queryset.filter(
                Q(application_no__icontains=keyword)
                | Q(reason__icontains=keyword)
                | Q(basis__icontains=keyword)
                | Q(archive__archive_code__icontains=keyword)
                | Q(archive__title__icontains=keyword)
                | Q(applicant__real_name__icontains=keyword)
            )

        status_value = (params.get("status") or "").strip()
        if status_value:
            queryset = queryset.filter(status=status_value)

        archive_code = (params.get("archive_code") or "").strip()
        if archive_code:
            queryset = queryset.filter(archive__archive_code__icontains=archive_code)

        if self.action == "retrieve":
            queryset = queryset.select_related(
                "execution_record",
                "execution_record__operator",
            ).prefetch_related(
                "approval_records__approver",
                "execution_record__attachments",
            )

        return queryset.distinct()

    def list(self, request, *args, **kwargs):
        return self.build_list_response()

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), context=self.get_serializer_context())
        return success_response(data=serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        application.refresh_from_db()
        return success_response(
            data=DestroyApplicationDetailSerializer(application, context=self.get_serializer_context()).data,
            message="销毁申请创建成功",
            code=status.HTTP_201_CREATED,
        )

    @decorators.action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        application = self.get_object()
        serializer = DestroyApprovalActionSerializer(
            data=request.data,
            context={"application": application, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        application.refresh_from_db()
        return success_response(
            data=DestroyApplicationDetailSerializer(application, context=self.get_serializer_context()).data,
            message="销毁审批处理成功",
        )

    @decorators.action(
        detail=True,
        methods=["post"],
        url_path="execute",
        parser_classes=[MultiPartParser, FormParser],
    )
    def execute(self, request, pk=None):
        application = self.get_object()
        serializer = DestroyExecutionSerializer(
            data=request.data,
            context={"application": application, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        application.refresh_from_db()
        return success_response(
            data=DestroyApplicationDetailSerializer(application, context=self.get_serializer_context()).data,
            message="销毁执行完成",
        )
