from rest_framework import serializers

from apps.notifications.models import SystemNotification
from apps.notifications.services import mark_notification_as_read, mark_notifications_as_read


class SystemNotificationSerializer(serializers.ModelSerializer):
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
