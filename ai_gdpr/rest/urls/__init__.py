from django.urls import include, path

urlpatterns = [
    path("webhook/", include("ai_gdpr.rest.urls.webhook")),
    path("config/", include("ai_gdpr.rest.urls.config")),
]
