from rest_framework.routers import DefaultRouter

from apps.destruction.api.views import DestroyApplicationViewSet


router = DefaultRouter()
router.register("applications", DestroyApplicationViewSet, basename="destroy-application")

urlpatterns = router.urls

