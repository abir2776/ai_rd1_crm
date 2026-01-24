from django.contrib import admin

from whatsapp_campaign.models import WhatsAppCampaignConfig, WhatsAppCampaignReport

admin.site.register(WhatsAppCampaignConfig)
admin.site.register(WhatsAppCampaignReport)
