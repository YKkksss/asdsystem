from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.archives.api.views import (
    ArchiveFileAccessContentAPIView,
    ArchiveFileDownloadTicketAPIView,
    ArchiveFilePreviewTicketAPIView,
    ArchiveRecordViewSet,
    ArchiveStorageLocationViewSet,
)


router = DefaultRouter()
router.register("storage-locations", ArchiveStorageLocationViewSet, basename="archive-storage-location")
router.register("records", ArchiveRecordViewSet, basename="archive-record")

urlpatterns = router.urls + [
    path("files/<int:file_id>/preview-ticket/", ArchiveFilePreviewTicketAPIView.as_view(), name="archive-file-preview-ticket"),
    path("files/<int:file_id>/download-ticket/", ArchiveFileDownloadTicketAPIView.as_view(), name="archive-file-download-ticket"),
    path("file-access/<str:token>/content/", ArchiveFileAccessContentAPIView.as_view(), name="archive-file-access-content"),
]
