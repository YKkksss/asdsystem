from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.audit.api.views import AuditLogViewSet, AuditSummaryAPIView


router = DefaultRouter()
router.register("logs", AuditLogViewSet, basename="audit-log")

urlpatterns = router.urls + [
    path("summary/", AuditSummaryAPIView.as_view(), name="audit-summary"),
]

