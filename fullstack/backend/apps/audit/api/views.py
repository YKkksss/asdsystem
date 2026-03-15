from django.db.models import Q
from rest_framework import mixins, viewsets
from rest_framework.views import APIView

from apps.audit.api.serializers import AuditLogSerializer
from apps.audit.models import AuditLog
from apps.audit.services import build_audit_summary
from apps.common.permissions import IsAuditViewer
from apps.common.pagination import OptionalPaginationListMixin
from apps.common.response import success_response


class AuditLogViewSet(
    OptionalPaginationListMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuditViewer]
    ordering_fields = ["created_at", "id"]

    def get_queryset(self):
        queryset = AuditLog.objects.order_by("-id")
        params = self.request.query_params

        keyword = (params.get("keyword") or "").strip()
        if keyword:
            queryset = queryset.filter(
                Q(username__icontains=keyword)
                | Q(real_name__icontains=keyword)
                | Q(target_repr__icontains=keyword)
                | Q(description__icontains=keyword)
            )

        module_name = (params.get("module_name") or "").strip()
        if module_name:
            queryset = queryset.filter(module_name=module_name)

        action_code = (params.get("action_code") or "").strip()
        if action_code:
            queryset = queryset.filter(action_code=action_code)

        result_status = (params.get("result_status") or "").strip()
        if result_status:
            queryset = queryset.filter(result_status=result_status)

        username = (params.get("username") or "").strip()
        if username:
            queryset = queryset.filter(username__icontains=username)

        biz_type = (params.get("biz_type") or "").strip()
        if biz_type:
            queryset = queryset.filter(biz_type=biz_type)

        return queryset

    def list(self, request, *args, **kwargs):
        return self.build_list_response()

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return success_response(data=serializer.data)


class AuditSummaryAPIView(APIView):
    permission_classes = [IsAuditViewer]

    def get(self, request):
        return success_response(data=build_audit_summary())
