from django.urls import path

from ..views import register

urlpatterns = [
    path(
        "forget_password",
        register.UserForgetPasswordAPIView.as_view(),
        name="user-forget-password",
    ),
    path(
        "register",
        register.PublicOrganizationRegistration.as_view(),
        name="organization-registration",
    ),
    path(
        "verify/<uuid:token>",
        register.UserVerificationAPIView.as_view(),
        name="user-verify",
    ),
]
