from django.urls import path

from apps.system.api.views import SystemHealthDetailView, SystemHealthView


urlpatterns = [
    path("health/", SystemHealthView.as_view(), name="system-health"),
    path("health/detail/", SystemHealthDetailView.as_view(), name="system-health-detail"),
]
