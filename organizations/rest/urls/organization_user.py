from django.urls import path

from ..views import organization_user

urlpatterns = [
    path(
        "",
        organization_user.OrganizationUserListView.as_view(),
        name="organization-user-list-create",
    )
]
