from django.urls import path

from whatsapp_campaign.rest.views.reports import WhatsAppCampaignReportListView

urlpatterns = [
    path("<uuid:campaign_uid>", WhatsAppCampaignReportListView.as_view(), name="whatsapp-campaign-reports")
]
