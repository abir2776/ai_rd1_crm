from django.urls import path

from ..views import register

urlpatterns = [
    path(
        "register",
        register.PublicOrganizationRegistration.as_view(),
        name="organization-registration",
    )
]
