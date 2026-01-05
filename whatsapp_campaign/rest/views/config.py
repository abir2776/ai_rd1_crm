from rest_framework.generics import DestroyAPIView, ListCreateAPIView

from whatsapp_campaign.models import WhatsAppCampaignConfig
from whatsapp_campaign.rest.serializers.config import WhatsAppCampaignConfigSerializer
from whatsapp_campaign.tasks import process_campaign


class WhatsappConfigListCreateView(ListCreateAPIView):
    serializer_class = WhatsAppCampaignConfigSerializer

    def get_queryset(self):
        organization = self.request.user.get_organization()
        return WhatsAppCampaignConfig.objects.filter(organization=organization)

    def perform_create(self, serializer):
        campaign = serializer.save()
        if campaign.schedule_type == "now":
            process_campaign.delay(campaign.id)


class WhatsappConfigDeleteView(DestroyAPIView):
    lookup_field = "uid"

    def get_queryset(self):
        organization = self.request.user.get_organization()
        return WhatsAppCampaignConfig.objects.filter(organization=organization)
