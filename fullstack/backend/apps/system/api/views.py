from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.common.permissions import IsSystemAdminOrInternalRequest
from apps.common.response import success_response
from apps.system.services import build_health_detail_payload, build_health_payload


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
    permission_classes = [IsSystemAdminOrInternalRequest]

    def get(self, request):
        return success_response(data=build_health_detail_payload())
