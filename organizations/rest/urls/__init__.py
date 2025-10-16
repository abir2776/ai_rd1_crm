from django.urls import path, include

urlpatterns = [
    path("/users", include("organizations.rest.urls.organization_user")),
    path("/invite", include("organizations.rest.urls.organization_user_invite")),
]
