from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView

from whatsapp_campaign.models import (
    WhatsAppCampaignConfig,
    WhatsAppCampaignReport,
)
from whatsapp_campaign.rest.serializers.reports import (
    WhatsAppCampaignReportSerializer,
)


class WhatsAppCampaignReportListView(ListAPIView):
    serializer_class = WhatsAppCampaignReportSerializer

    def get_queryset(self):
        organization = self.request.user.get_organization()
        campaign_uid = self.kwargs.get("campaign_uid")

        campaign = get_object_or_404(
            WhatsAppCampaignConfig,
            uid=campaign_uid,
            organization=organization,
        )
        return WhatsAppCampaignReport.objects.filter(campaign=campaign)

