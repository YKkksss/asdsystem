from django.db.models import Q
from rest_framework import decorators, mixins, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.borrowing.api.serializers import (
    BorrowApplicationDetailSerializer,
    BorrowApplicationListSerializer,
    BorrowApplicationWriteSerializer,
    BorrowApprovalActionSerializer,
    BorrowCheckoutSerializer,
    BorrowReturnConfirmSerializer,
    BorrowReturnSubmitSerializer,
)
from apps.borrowing.models import BorrowApplication, BorrowApplicationStatus
from apps.borrowing.services import (
    BIZ_TYPE_BORROW_APPLICATION,
    dispatch_due_borrow_reminders,
    is_admin_or_auditor_user,
    is_archive_manager_user,
    sync_overdue_borrow_applications,
)
from apps.audit.services import record_audit_log
from apps.common.permissions import IsArchiveManager
from apps.common.pagination import OptionalPaginationListMixin
from apps.common.response import success_response
from apps.notifications.models import SystemNotification


class BorrowApplicationViewSet(
    OptionalPaginationListMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = BorrowApplication.objects.select_related(
        "archive",
        "applicant",
        "applicant_dept",
        "current_approver",
        "return_record",
    ).order_by("-id")
    search_fields = ["application_no", "purpose", "archive__archive_code", "archive__title", "applicant__real_name"]
    ordering_fields = ["id", "created_at", "expected_return_at", "submitted_at", "approved_at", "checkout_at", "returned_at"]
    filterset_fields = ["status", "archive_id", "applicant_id", "applicant_dept_id", "current_approver_id", "is_overdue"]

    def get_permissions(self):
        if self.action in {"checkout", "confirm_return"}:
            permission_classes = [IsArchiveManager]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == "create":
            return BorrowApplicationWriteSerializer
        if self.action == "retrieve":
            return BorrowApplicationDetailSerializer
        return BorrowApplicationListSerializer

    def get_queryset(self):
        sync_overdue_borrow_applications()
        queryset = super().get_queryset()
        params = self.request.query_params
        user = self.request.user
        notified_application_ids = SystemNotification.objects.filter(
            user=user,
            biz_type=BIZ_TYPE_BORROW_APPLICATION,
            biz_id__isnull=False,
        ).values_list("biz_id", flat=True)

        scope = (params.get("scope") or "").strip().lower()
        if scope == "mine":
            queryset = queryset.filter(applicant_id=user.id)
        elif scope == "approval":
            queryset = queryset.filter(
                current_approver_id=user.id,
                status=BorrowApplicationStatus.PENDING_APPROVAL,
            )
        elif scope == "checkout":
            if not is_archive_manager_user(user):
                queryset = queryset.none()
            else:
                queryset = queryset.filter(status=BorrowApplicationStatus.APPROVED)
        elif scope == "return":
            if is_archive_manager_user(user):
                queryset = queryset.filter(return_record__return_status="SUBMITTED")
            else:
                queryset = queryset.filter(applicant_id=user.id)
        elif scope == "all":
            if not (is_archive_manager_user(user) or is_admin_or_auditor_user(user)):
                queryset = queryset.filter(Q(applicant_id=user.id) | Q(id__in=notified_application_ids))
        else:
            if not (is_archive_manager_user(user) or is_admin_or_auditor_user(user)):
                queryset = queryset.filter(
                    Q(applicant_id=user.id)
                    | Q(current_approver_id=user.id)
                    | Q(id__in=notified_application_ids)
                )

        keyword = (params.get("keyword") or "").strip()
        if keyword:
            queryset = queryset.filter(
                Q(application_no__icontains=keyword)
                | Q(purpose__icontains=keyword)
                | Q(archive__archive_code__icontains=keyword)
                | Q(archive__title__icontains=keyword)
                | Q(applicant__real_name__icontains=keyword)
            )

        archive_code = (params.get("archive_code") or "").strip()
        if archive_code:
            queryset = queryset.filter(archive__archive_code__icontains=archive_code)

        status_value = (params.get("status") or "").strip()
        if status_value:
            queryset = queryset.filter(status=status_value)

        status_in_values = [item.strip() for item in (params.get("status_in") or "").split(",") if item.strip()]
        if status_in_values:
            queryset = queryset.filter(status__in=status_in_values)

        if self.action == "retrieve":
            queryset = queryset.select_related(
                "return_record__returned_by_user",
                "return_record__received_by_user",
                "return_record__location_after_return",
                "checkout_record__borrower",
                "checkout_record__operator",
            ).prefetch_related(
                "approval_records__approver",
                "return_record__attachments",
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
            data=BorrowApplicationDetailSerializer(application, context=self.get_serializer_context()).data,
            message="借阅申请创建成功",
            code=status.HTTP_201_CREATED,
        )

    @decorators.action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        application = self.get_object()
        serializer = BorrowApprovalActionSerializer(
            data=request.data,
            context={"application": application, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        application.refresh_from_db()
        return success_response(
            data=BorrowApplicationDetailSerializer(application, context=self.get_serializer_context()).data,
            message="借阅审批处理成功",
        )

    @decorators.action(detail=True, methods=["post"], url_path="checkout")
    def checkout(self, request, pk=None):
        application = self.get_object()
        serializer = BorrowCheckoutSerializer(
            data=request.data,
            context={"application": application, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        application.refresh_from_db()
        return success_response(
            data=BorrowApplicationDetailSerializer(application, context=self.get_serializer_context()).data,
            message="借阅出库登记成功",
        )

    @decorators.action(
        detail=True,
        methods=["post"],
        url_path="submit-return",
        parser_classes=[MultiPartParser, FormParser],
    )
    def submit_return(self, request, pk=None):
        application = self.get_object()
        serializer = BorrowReturnSubmitSerializer(
            data=request.data,
            context={"application": application, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        application.refresh_from_db()
        return success_response(
            data=BorrowApplicationDetailSerializer(application, context=self.get_serializer_context()).data,
            message="归还提交成功",
        )

    @decorators.action(detail=True, methods=["post"], url_path="confirm-return")
    def confirm_return(self, request, pk=None):
        application = self.get_object()
        serializer = BorrowReturnConfirmSerializer(
            data=request.data,
            context={"application": application, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        application = serializer.save()
        application.refresh_from_db()
        return success_response(
            data=BorrowApplicationDetailSerializer(application, context=self.get_serializer_context()).data,
            message="归还确认处理成功",
        )


class BorrowReminderDispatchAPIView(APIView):
    permission_classes = [IsArchiveManager]

    def post(self, request):
        reminder_records = dispatch_due_borrow_reminders()
        record_audit_log(
            module_name="BORROWING",
            action_code="BORROW_REMINDER_DISPATCH",
            description="手工触发借阅催还扫描任务。",
            user=request.user,
            biz_type="borrow_reminder",
            biz_id=None,
            target_repr="manual-dispatch",
            request=request,
            extra_data={"record_count": len(reminder_records)},
        )
        return success_response(
            data={"record_count": len(reminder_records)},
            message="催还扫描执行完成",
        )
