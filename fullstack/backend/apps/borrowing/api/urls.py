from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.borrowing.api.views import BorrowApplicationViewSet, BorrowReminderDispatchAPIView


router = DefaultRouter()
router.register("applications", BorrowApplicationViewSet, basename="borrow-application")

urlpatterns = router.urls + [
    path("reminders/dispatch/", BorrowReminderDispatchAPIView.as_view(), name="borrow-reminder-dispatch"),
]
