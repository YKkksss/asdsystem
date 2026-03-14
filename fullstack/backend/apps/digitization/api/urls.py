from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.digitization.api.views import (
    ScanTaskAssigneeAPIView,
    ScanTaskItemUploadAPIView,
    ScanTaskViewSet,
)


router = DefaultRouter()
router.register("scan-tasks", ScanTaskViewSet, basename="scan-task")

urlpatterns = router.urls + [
    path("scan-task-assignees/", ScanTaskAssigneeAPIView.as_view(), name="scan-task-assignees"),
    path(
        "scan-task-items/<int:item_id>/upload-files/",
        ScanTaskItemUploadAPIView.as_view(),
        name="scan-task-item-upload-files",
    ),
]
