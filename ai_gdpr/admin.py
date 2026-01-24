from django.contrib import admin

from ai_gdpr.models import GDPREmailConfig, GDPREmailTracker

admin.site.register(GDPREmailTracker)
admin.site.register(GDPREmailConfig)
