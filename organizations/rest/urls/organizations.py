from django.urls import path

from ..views import organizations

urlpatterns = [
    path(
        "me",
        organizations.OrganizationProfileView.as_view(),
        name="organization-profile",
    ),
    path(
        "my_organizations",
        organizations.MyOrganizationListView.as_view(),
        name="my-organization-list",
    ),
    path(
        "switch/<uuid:uid>",
        organizations.OrganizationSwitchAPIView.as_view(),
        name="organization-switch",
    ),
]
