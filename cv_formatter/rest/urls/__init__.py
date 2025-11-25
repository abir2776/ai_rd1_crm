from django.urls import include, path

urlpatterns = [path("config", include("cv_formatter.rest.urls.config"))]
