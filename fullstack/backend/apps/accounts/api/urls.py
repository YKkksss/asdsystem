from rest_framework.routers import DefaultRouter

from apps.accounts.api.views import RoleViewSet, SystemPermissionViewSet, UserViewSet


router = DefaultRouter()
router.register("roles", RoleViewSet, basename="role")
router.register("permissions", SystemPermissionViewSet, basename="permission")
router.register("users", UserViewSet, basename="user")

urlpatterns = router.urls
