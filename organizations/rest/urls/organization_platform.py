from django.urls import path

from ..views import organization_platform

urlpatterns = [
    path(
        "connect",
        organization_platform.ConnectPlatformView.as_view(),
        name="organization-platform-connect",
    )
]
