from rest_framework import serializers

from apps.notifications.models import SystemNotification
from apps.notifications.services import (
    mark_notification_as_read,
    mark_notifications_as_read,
    resolve_notification_route_path,
)


class SystemNotificationSerializer(serializers.ModelSerializer):
    route_path = serializers.SerializerMethodField()

    def get_route_path(self, obj: SystemNotification) -> str:
        return resolve_notification_route_path(obj)

    class Meta:
        model = SystemNotification
        fields = [
            "id",
            "notification_type",
            "title",
            "content",
            "biz_type",
            "biz_id",
            "is_read",
            "read_at",
            "created_at",
            "updated_at",
            "route_path",
        ]
        read_only_fields = fields


class MarkNotificationReadSerializer(serializers.Serializer):
    def save(self, **kwargs) -> SystemNotification:
        notification = self.context["notification"]
        return mark_notification_as_read(notification=notification)


class MarkAllNotificationsReadSerializer(serializers.Serializer):
    def save(self, **kwargs) -> int:
        user = self.context["user"]
        return mark_notifications_as_read(user=user)
