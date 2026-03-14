import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse
from django.urls import reverse
from django.db.models import Q
from rest_framework import decorators, mixins, status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError

from apps.archives.api.serializers import (
    ArchiveBatchPrintSerializer,
    ArchiveFileDownloadTicketSerializer,
    ArchiveRecordDetailSerializer,
    ArchiveRecordListSerializer,
    ArchiveRecordWriteSerializer,
    ArchiveStatusTransitionSerializer,
    ArchiveStorageLocationSerializer,
)
from apps.archives.models import ArchiveFile, ArchiveRecord, ArchiveStorageLocation
from apps.archives.services import (
    batch_print_archive_codes,
    generate_archive_codes,
    issue_archive_file_download_ticket_for_user,
    issue_archive_file_preview_ticket_for_user,
    print_archive_codes,
)
from apps.audit.models import ArchiveFileAccessAction
from apps.audit.services import mark_archive_file_access_ticket_used, record_audit_log, validate_archive_file_access_ticket
from apps.common.permissions import IsArchiveManager
from apps.common.response import error_response, success_response


class ArchiveStorageLocationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = ArchiveStorageLocation.objects.order_by(
        "warehouse_name",
        "cabinet_code",
        "rack_code",
        "layer_code",
        "box_code",
        "id",
    )
    serializer_class = ArchiveStorageLocationSerializer
    search_fields = ["warehouse_name", "area_name", "cabinet_code", "rack_code", "box_code", "full_location_code"]
    ordering_fields = ["created_at", "updated_at", "id"]
    filterset_fields = ["warehouse_name", "cabinet_code", "status"]

    def get_permissions(self):
        permission_classes = [IsArchiveManager]
        return [permission() for permission in permission_classes]

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.filter_queryset(self.get_queryset()), many=True)
        return success_response(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return success_response(data=serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = serializer.save(created_by=request.user.id, updated_by=request.user.id)
        return success_response(
            data=self.get_serializer(location).data,
            message="实体位置创建成功",
            code=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        location = serializer.save(updated_by=request.user.id)
        return success_response(data=self.get_serializer(location).data, message="实体位置更新成功")


class ArchiveRecordViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = (
        ArchiveRecord.objects.select_related("responsible_dept", "location")
        .prefetch_related("barcodes", "revisions", "files")
        .order_by("id")
    )
    search_fields = ["archive_code", "title", "keywords", "responsible_person"]
    ordering_fields = ["id", "created_at", "updated_at", "year"]
    filterset_fields = ["status", "year", "retention_period", "security_level", "responsible_dept", "location"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        keyword = (params.get("keyword") or params.get("search") or "").strip()
        if keyword:
            queryset = queryset.filter(
                Q(archive_code__icontains=keyword)
                | Q(title__icontains=keyword)
                | Q(keywords__icontains=keyword)
                | Q(summary__icontains=keyword)
                | Q(responsible_person__icontains=keyword)
                | Q(files__extracted_text__icontains=keyword)
            )

        archive_code = params.get("archive_code")
        if archive_code:
            queryset = queryset.filter(archive_code__icontains=archive_code.strip())

        year = params.get("year")
        if year:
            queryset = queryset.filter(year=year)

        retention_period = params.get("retention_period")
        if retention_period:
            queryset = queryset.filter(retention_period=retention_period.strip())

        security_level = params.get("security_level")
        if security_level:
            queryset = queryset.filter(security_level=security_level.strip())

        status_value = params.get("status")
        if status_value:
            queryset = queryset.filter(status=status_value.strip())

        responsible_dept_id = params.get("responsible_dept_id")
        if responsible_dept_id:
            queryset = queryset.filter(responsible_dept_id=responsible_dept_id)

        location_id = params.get("location_id")
        if location_id:
            queryset = queryset.filter(location_id=location_id)

        return queryset.distinct()

    def get_permissions(self):
        if self.action in {"list", "retrieve"}:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsArchiveManager]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action in {"create", "update", "partial_update"}:
            return ArchiveRecordWriteSerializer
        if self.action == "retrieve":
            return ArchiveRecordDetailSerializer
        return ArchiveRecordListSerializer

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.filter_queryset(self.get_queryset()), many=True)
        return success_response(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return success_response(data=serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        archive = serializer.save()
        return success_response(
            data=ArchiveRecordDetailSerializer(archive, context=self.get_serializer_context()).data,
            message="档案创建成功",
            code=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(
            self.get_object(),
            data=request.data,
            partial=partial,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        archive = serializer.save()
        archive.refresh_from_db()
        return success_response(
            data=ArchiveRecordDetailSerializer(archive, context=self.get_serializer_context()).data,
            message="档案更新成功",
        )

    @decorators.action(detail=True, methods=["post"], url_path="generate-codes")
    def generate_codes(self, request, pk=None):
        archive = self.get_object()
        generate_archive_codes(archive=archive, operator_id=request.user.id)
        archive.refresh_from_db()
        return success_response(
            data=ArchiveRecordDetailSerializer(archive, context=self.get_serializer_context()).data,
            message="档案条码与二维码生成成功",
        )

    @decorators.action(detail=True, methods=["post"], url_path="print-codes")
    def print_codes(self, request, pk=None):
        archive = self.get_object()
        print_archive_codes(archive=archive, operator_id=request.user.id)
        archive.refresh_from_db()
        return success_response(
            data=ArchiveRecordDetailSerializer(archive, context=self.get_serializer_context()).data,
            message="档案条码打印留痕成功",
        )

    @decorators.action(detail=False, methods=["post"], url_path="batch-print-codes")
    def batch_print_codes(self, request):
        serializer = ArchiveBatchPrintSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        archives = batch_print_archive_codes(
            archive_ids=serializer.validated_data["archive_ids"],
            operator_id=request.user.id,
        )
        return success_response(
            data=ArchiveRecordDetailSerializer(
                archives,
                many=True,
                context=self.get_serializer_context(),
            ).data,
            message="档案批量打印留痕成功",
        )

    @decorators.action(detail=True, methods=["post"], url_path="transition-status")
    def transition_status(self, request, pk=None):
        archive = self.get_object()
        serializer = ArchiveStatusTransitionSerializer(
            data=request.data,
            context={"archive": archive, "request": request},
        )
        serializer.is_valid(raise_exception=True)
        archive = serializer.save()
        archive.refresh_from_db()
        return success_response(
            data=ArchiveRecordDetailSerializer(archive, context=self.get_serializer_context()).data,
            message="档案状态流转成功",
        )


class ArchiveFilePreviewTicketAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, file_id: int):
        archive_file = ArchiveFile.objects.select_related("archive").filter(id=file_id).first()
        if not archive_file:
            return error_response("档案文件不存在。", status.HTTP_404_NOT_FOUND)

        try:
            ticket = issue_archive_file_preview_ticket_for_user(
                archive_file=archive_file,
                user=request.user,
                request=request,
            )
        except ValidationError as exc:
            return error_response(str(exc.detail[0] if isinstance(exc.detail, list) else exc.detail), status.HTTP_400_BAD_REQUEST)

        access_url = reverse("archive-file-access-content", kwargs={"token": ticket.token})
        return success_response(
            data={
                "access_url": access_url,
                "watermark_text": ticket.watermark_text,
                "expires_at": ticket.expires_at.isoformat(),
                "file_name": archive_file.file_name,
                "file_ext": archive_file.file_ext,
            },
            message="预览票据签发成功",
        )


class ArchiveFileDownloadTicketAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, file_id: int):
        archive_file = ArchiveFile.objects.select_related("archive").filter(id=file_id).first()
        if not archive_file:
            return error_response("档案文件不存在。", status.HTTP_404_NOT_FOUND)

        serializer = ArchiveFileDownloadTicketSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            ticket = issue_archive_file_download_ticket_for_user(
                archive_file=archive_file,
                user=request.user,
                purpose=serializer.validated_data["purpose"].strip(),
                request=request,
            )
        except ValidationError as exc:
            return error_response(str(exc.detail[0] if isinstance(exc.detail, list) else exc.detail), status.HTTP_400_BAD_REQUEST)

        access_url = reverse("archive-file-access-content", kwargs={"token": ticket.token})
        return success_response(
            data={
                "access_url": access_url,
                "expires_at": ticket.expires_at.isoformat(),
                "file_name": archive_file.file_name,
                "purpose": ticket.purpose,
            },
            message="下载票据签发成功",
        )


class ArchiveFileAccessContentAPIView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token: str):
        try:
            ticket = validate_archive_file_access_ticket(token=token)
        except ValidationError as exc:
            return error_response(str(exc.detail[0] if isinstance(exc.detail, list) else exc.detail), status.HTTP_400_BAD_REQUEST)

        archive_file = ticket.archive_file
        absolute_path = Path(settings.MEDIA_ROOT) / archive_file.file_path
        if not absolute_path.exists():
            return error_response("档案文件不存在或已被移除。", status.HTTP_404_NOT_FOUND)

        mark_archive_file_access_ticket_used(ticket=ticket)
        record_audit_log(
            module_name="ARCHIVES",
            action_code="ARCHIVE_FILE_PREVIEW_ACCESS"
            if ticket.access_action == ArchiveFileAccessAction.PREVIEW
            else "ARCHIVE_FILE_DOWNLOAD_ACCESS",
            description="访问档案文件预览内容。"
            if ticket.access_action == ArchiveFileAccessAction.PREVIEW
            else "下载档案文件内容。",
            user=ticket.user,
            username=ticket.username,
            real_name=ticket.real_name,
            biz_type="archive_file",
            biz_id=archive_file.id,
            target_repr=f"{archive_file.archive.archive_code}/{archive_file.file_name}",
            request=request,
            extra_data={
                "access_action": ticket.access_action,
                "purpose": ticket.purpose,
            },
        )

        content_type = archive_file.mime_type or mimetypes.guess_type(absolute_path.name)[0] or "application/octet-stream"
        response = FileResponse(
            absolute_path.open("rb"),
            as_attachment=ticket.access_action == ArchiveFileAccessAction.DOWNLOAD,
            filename=archive_file.file_name,
            content_type=content_type,
        )
        response["Cache-Control"] = "no-store"
        return response
