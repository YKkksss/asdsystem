from rest_framework import decorators, mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.common.permissions import IsSystemAdmin
from apps.common.response import success_response
from apps.organizations.api.serializers import DepartmentSerializer
from apps.organizations.models import Department
from apps.organizations.services import build_department_tree


class DepartmentViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Department.objects.select_related("parent").order_by("sort_order", "id")
    serializer_class = DepartmentSerializer
    search_fields = ["dept_code", "dept_name"]
    ordering_fields = ["sort_order", "created_at", "id"]

    def get_permissions(self):
        if self.action in {"list", "retrieve", "tree"}:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsSystemAdmin]
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
        department = serializer.save(created_by=request.user.id, updated_by=request.user.id)
        return success_response(
            data=self.get_serializer(department).data,
            message="部门创建成功",
            code=status.HTTP_201_CREATED,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        department = serializer.save(updated_by=request.user.id)
        return success_response(data=self.get_serializer(department).data, message="部门更新成功")

    @decorators.action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request):
        departments = list(self.filter_queryset(self.get_queryset()))
        return success_response(data=build_department_tree(departments))
