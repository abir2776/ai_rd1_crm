from django.urls import path

from ..views import organizations

urlpatterns = [
    path(
        "me",
        organizations.OrganizationProfileView.as_view(),
        name="organization-profile",
    )
]
