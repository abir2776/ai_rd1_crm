from django.urls import include, path

urlpatterns = [path("config/", include("ai_lead_generation.rest.urls.config"))]
