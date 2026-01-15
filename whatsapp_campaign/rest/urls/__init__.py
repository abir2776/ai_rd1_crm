from django.urls import include, path

urlpatterns = [
    path("config/", include("whatsapp_campaign.rest.urls.config")),
    path("reports/", include("whatsapp_campaign.rest.urls.reports")),
    path("list/", include("whatsapp_campaign.rest.urls.list")),
]
