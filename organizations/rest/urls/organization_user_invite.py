from django.urls import path

from ..views import organization_user_invite

urlpatterns = [
    path(
        "",
        organization_user_invite.OrganizationUserInviteListCreateView.as_view(),
        name="organization-user-invite",
    ),
    path(
        "accept/<uuid:token>",
        organization_user_invite.OrganizationUserInviteAcceptAPIView.as_view(),
        name="invitation-accept",
    ),
]
