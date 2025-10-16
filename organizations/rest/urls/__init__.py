from django.urls import path, include

urlpatterns = [
    path("/invite", include("organizations.rest.urls.organization_user_invite"))
]
