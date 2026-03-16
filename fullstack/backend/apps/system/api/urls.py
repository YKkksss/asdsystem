from django.urls import path

from apps.system.api.views import SystemDashboardView, SystemHealthDetailView, SystemHealthView


urlpatterns = [
    path("dashboard/", SystemDashboardView.as_view(), name="system-dashboard"),
    path("health/", SystemHealthView.as_view(), name="system-health"),
    path("health/detail/", SystemHealthDetailView.as_view(), name="system-health-detail"),
]
