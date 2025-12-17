from django.urls import include, path

urlpatterns = [
    path("config/", include("awr_compliance.rest.urls.config")),
]
