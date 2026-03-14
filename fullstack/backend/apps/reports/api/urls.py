from django.urls import path

from apps.reports.api.views import (
    ReportArchiveAPIView,
    ReportDepartmentAPIView,
    ReportExportAPIView,
    ReportSummaryAPIView,
)


urlpatterns = [
    path("summary/", ReportSummaryAPIView.as_view(), name="report-summary"),
    path("departments/", ReportDepartmentAPIView.as_view(), name="report-departments"),
    path("archives/", ReportArchiveAPIView.as_view(), name="report-archives"),
    path("export/", ReportExportAPIView.as_view(), name="report-export"),
]

