from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView

from apps.common.permissions import HasConfiguredSystemPermission
from apps.common.response import success_response
from apps.system.services import build_dashboard_payload, build_health_detail_payload, build_health_payload


class RootHealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return success_response(data=build_health_payload(include_message=True))


class SystemHealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return success_response(data=build_health_payload(include_message=False))


class SystemHealthDetailView(APIView):
    permission_classes = [HasConfiguredSystemPermission]
    required_permission_codes = {"button.system.health.detail"}
    permission_fallback_roles = {"ADMIN"}

    def get(self, request):
        return success_response(data=build_health_detail_payload())


class SystemDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success_response(data=build_dashboard_payload(request.user))
