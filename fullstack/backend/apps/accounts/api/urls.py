from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.accounts.api.views import PermissionTemplateAPIView, RoleViewSet, SystemPermissionViewSet, UserViewSet


router = DefaultRouter()
router.register("roles", RoleViewSet, basename="role")
router.register("permissions", SystemPermissionViewSet, basename="permission")
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("permission-templates/", PermissionTemplateAPIView.as_view(), name="permission-template-list"),
    *router.urls,
]
