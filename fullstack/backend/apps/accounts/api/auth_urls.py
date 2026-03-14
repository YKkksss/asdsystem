from django.urls import path

from apps.accounts.api.views import LoginAPIView, LogoutAPIView, ProfileAPIView, RefreshTokenAPIView, UnlockUserAPIView


urlpatterns = [
    path("login/", LoginAPIView.as_view(), name="auth-login"),
    path("logout/", LogoutAPIView.as_view(), name="auth-logout"),
    path("refresh/", RefreshTokenAPIView.as_view(), name="auth-refresh"),
    path("profile/", ProfileAPIView.as_view(), name="auth-profile"),
    path("unlock/<int:user_id>/", UnlockUserAPIView.as_view(), name="auth-unlock"),
]
