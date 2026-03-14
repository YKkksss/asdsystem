from django.conf import settings
from django.contrib import admin
from django.conf.urls.static import static
from django.urls import include, path

from apps.system.api.views import RootHealthView


urlpatterns = [
    path("", RootHealthView.as_view(), name="root-health"),
    path("api/v1/auth/", include("apps.accounts.api.auth_urls")),
    path("api/v1/accounts/", include("apps.accounts.api.urls")),
    path("api/v1/audit/", include("apps.audit.api.urls")),
    path("api/v1/archives/", include("apps.archives.api.urls")),
    path("api/v1/borrowing/", include("apps.borrowing.api.urls")),
    path("api/v1/destruction/", include("apps.destruction.api.urls")),
    path("api/v1/digitization/", include("apps.digitization.api.urls")),
    path("api/v1/notifications/", include("apps.notifications.api.urls")),
    path("api/v1/organizations/", include("apps.organizations.api.urls")),
    path("api/v1/reports/", include("apps.reports.api.urls")),
    path("api/v1/system/", include("apps.system.api.urls")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
