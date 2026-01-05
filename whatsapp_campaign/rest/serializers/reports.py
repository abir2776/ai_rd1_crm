from rest_framework import serializers

from whatsapp_campaign.models import WhatsAppCampaignReport


class WhatsAppCampaignReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppCampaignReport
        fields = "__all__"
