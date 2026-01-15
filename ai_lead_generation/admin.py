from django.contrib import admin

from .models import LeadGenerationConfig, MarketingAutomationConfig

admin.site.register(LeadGenerationConfig)
admin.site.register(MarketingAutomationConfig)
