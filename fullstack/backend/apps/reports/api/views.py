from django.http import HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.audit.services import record_audit_log
from apps.common.permissions import IsReportViewer
from apps.common.response import success_response
from apps.notifications.models import NotificationType
from apps.notifications.services import create_system_notification
from apps.reports.api.serializers import ReportExportSerializer, ReportFilterSerializer
from apps.reports.services import (
    build_archive_utilization_report,
    build_department_report,
    build_report_filters,
    build_report_summary,
    export_rows_to_csv,
    serialize_report_filters,
)


class ReportSummaryAPIView(APIView):
    permission_classes = [IsAuthenticated, IsReportViewer]

    def get(self, request):
        serializer = ReportFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = build_report_filters(serializer.validated_data)
        return success_response(data=build_report_summary(filters))


class ReportDepartmentAPIView(APIView):
    permission_classes = [IsAuthenticated, IsReportViewer]

    def get(self, request):
        serializer = ReportFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = build_report_filters(serializer.validated_data)
        return success_response(data=build_department_report(filters))


class ReportArchiveAPIView(APIView):
    permission_classes = [IsAuthenticated, IsReportViewer]

    def get(self, request):
        serializer = ReportFilterSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = build_report_filters(serializer.validated_data)
        return success_response(data=build_archive_utilization_report(filters))


class ReportExportAPIView(APIView):
    permission_classes = [IsAuthenticated, IsReportViewer]

    def get(self, request):
        serializer = ReportExportSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        filters = build_report_filters(serializer.validated_data)
        report_type = serializer.validated_data["report_type"]

        if report_type == "departments":
            rows = build_department_report(filters)
            headers = [
                "applicant_dept_id",
                "applicant_dept_name",
                "borrow_count",
                "overdue_count",
                "returned_count",
                "overdue_rate",
            ]
            file_name = "department_borrow_report.csv"
            description = "导出部门借阅统计报表。"
        else:
            rows = build_archive_utilization_report(filters)
            headers = [
                "rank",
                "archive_id",
                "archive_code",
                "archive_title",
                "security_level",
                "status",
                "carrier_type",
                "borrow_count",
                "overdue_count",
                "returned_count",
                "latest_borrowed_at",
            ]
            file_name = "archive_utilization_report.csv"
            description = "导出档案利用率统计报表。"

        record_audit_log(
            module_name="REPORTS",
            action_code="REPORT_EXPORT",
            description=description,
            user=request.user,
            biz_type="report_export",
            biz_id=None,
            target_repr=report_type,
            request=request,
            extra_data={"report_type": report_type, "filters": serialize_report_filters(filters), "row_count": len(rows)},
        )
        create_system_notification(
            user=request.user,
            notification_type=NotificationType.SYSTEM,
            title="报表导出已完成",
            content=f"{description} 导出成功，可进入报表中心继续查看与复核结果。",
            biz_type="report_export",
        )

        content = export_rows_to_csv(headers=headers, rows=rows)
        response = HttpResponse(content, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        return response
