from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.notifications.api.views import NotificationSummaryAPIView, SystemNotificationViewSet


router = DefaultRouter()
router.register("messages", SystemNotificationViewSet, basename="notification")

urlpatterns = router.urls + [
    path("summary/", NotificationSummaryAPIView.as_view(), name="notification-summary"),
]

