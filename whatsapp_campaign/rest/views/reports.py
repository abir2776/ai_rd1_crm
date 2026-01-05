from rest_framework.generics import ListAPIView

from whatsapp_campaign.models import WhatsAppCampaignReport
from whatsapp_campaign.rest.serializers.reports import WhatsAppCampaignReportSerializer


class WhatsAppCampaignReportListView(ListAPIView):
    serializer_class = WhatsAppCampaignReportSerializer

    def get_queryset(self):
        organization = self.request.user.get_organization()
        return WhatsAppCampaignReport.objects.filter(
            campaign__organization=organization
        )
