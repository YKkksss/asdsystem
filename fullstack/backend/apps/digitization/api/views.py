from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.permissions import IsArchiveManager
from apps.common.pagination import OptionalPaginationListMixin
from apps.common.response import error_response, success_response
from apps.digitization.api.serializers import (
    ScanAssigneeSerializer,
    ScanTaskDetailSerializer,
    ScanTaskListSerializer,
    ScanTaskWriteSerializer,
)
from apps.digitization.models import ScanTask, ScanTaskItem
from apps.digitization.services import upload_files_to_scan_task_item


User = get_user_model()


class ScanTaskViewSet(OptionalPaginationListMixin, viewsets.GenericViewSet):
    queryset = ScanTask.objects.order_by("-id")
    search_fields = ["task_no", "task_name", "remark"]
    ordering_fields = ["id", "created_at", "started_at", "finished_at"]
    filterset_fields = ["status", "assigned_user_id"]

    def get_permissions(self):
        permission_classes = [IsArchiveManager]
        return [permission() for permission in permission_classes]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ScanTaskDetailSerializer
        if self.action == "create":
            return ScanTaskWriteSerializer
        return ScanTaskListSerializer

    def list(self, request, *args, **kwargs):
        return self.build_list_response()

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return success_response(data=serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        task = serializer.save()
        return success_response(
            data=ScanTaskDetailSerializer(task).data,
            message="扫描任务创建成功",
            code=status.HTTP_201_CREATED,
        )

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "retrieve":
            return queryset.prefetch_related("items__archive")
        return queryset

    def list_assignees(self, request):
        users = User.objects.filter(status=True, is_staff=True).order_by("id").values(
            "id",
            "username",
            "real_name",
            "dept_id",
        )
        serializer = ScanAssigneeSerializer(users, many=True)
        return success_response(data=serializer.data)


class ScanTaskAssigneeAPIView(APIView):
    permission_classes = [IsArchiveManager]

    def get(self, request):
        users = User.objects.filter(status=True, is_staff=True).order_by("id").values(
            "id",
            "username",
            "real_name",
            "dept_id",
        )
        serializer = ScanAssigneeSerializer(users, many=True)
        return success_response(data=serializer.data)


class ScanTaskItemUploadAPIView(APIView):
    permission_classes = [IsArchiveManager]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, item_id: int):
        task_item = ScanTaskItem.objects.select_related("task", "archive").filter(id=item_id).first()
        if not task_item:
            return error_response("扫描任务明细不存在。", status.HTTP_404_NOT_FOUND)

        files = request.FILES.getlist("files")
        if not files:
            return error_response("至少需要上传一个文件。", status.HTTP_400_BAD_REQUEST)

        task_item = upload_files_to_scan_task_item(
            task_item=task_item,
            uploaded_files=files,
            operator_id=request.user.id,
        )
        task_item.refresh_from_db()
        task_item.task.refresh_from_db()
        return success_response(
            data=ScanTaskDetailSerializer(task_item.task).data,
            message="扫描文件上传成功",
        )
