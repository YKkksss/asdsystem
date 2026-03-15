from rest_framework import decorators, mixins, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.pagination import OptionalPaginationListMixin
from apps.common.response import success_response
from apps.notifications.api.serializers import (
    MarkAllNotificationsReadSerializer,
    MarkNotificationReadSerializer,
    SystemNotificationSerializer,
)
from apps.notifications.models import SystemNotification
from apps.notifications.services import build_notification_summary


class SystemNotificationViewSet(
    OptionalPaginationListMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SystemNotificationSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ["created_at", "read_at", "id"]

    def get_queryset(self):
        queryset = SystemNotification.objects.filter(user=self.request.user).order_by("is_read", "-created_at", "-id")
        notification_type = (self.request.query_params.get("notification_type") or "").strip()
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        read_status = (self.request.query_params.get("is_read") or "").strip().lower()
        if read_status in {"true", "false"}:
            queryset = queryset.filter(is_read=read_status == "true")
        return queryset

    def list(self, request, *args, **kwargs):
        return self.build_list_response()

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return success_response(data=serializer.data)

    @decorators.action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        serializer = MarkAllNotificationsReadSerializer(context={"user": request.user})
        updated_count = serializer.save()
        return success_response(data={"updated_count": updated_count}, message="通知已全部标记为已读")

    @decorators.action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        serializer = MarkNotificationReadSerializer(context={"notification": notification})
        notification = serializer.save()
        return success_response(data=SystemNotificationSerializer(notification).data, message="通知已标记为已读")


class NotificationSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(data=build_notification_summary(request.user))
