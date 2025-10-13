from django.urls import path, include

urlpatterns = [path("/users", include("organizations.rest.urls.organization_user"))]
