from django.urls import path

from ..views import register

urlpatterns = [
    path(
        "register",
        register.PublicOrganizationRegistration.as_view(),
        name="organization-registration",
    ),
    path(
        "/verify/<int:token>",
        register.UserVerificationAPIView.as_view(),
        name="user-verify",
    ),
]
