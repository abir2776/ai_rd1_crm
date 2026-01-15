from django.urls import path

from whatsapp_campaign.rest.views.config import (
    WhatsappConfigDeleteView,
    WhatsappConfigListCreateView,
)

urlpatterns = [
    path("", WhatsappConfigListCreateView.as_view(), name="whatsapp-campaign"),
    path(
        "<uuid:uid>",
        WhatsappConfigDeleteView.as_view(),
        name="whatsapp-campaign-delete",
    ),
]
