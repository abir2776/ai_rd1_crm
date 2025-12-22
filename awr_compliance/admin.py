from django.contrib import admin

from awr_compliance.models import AWRConfig, AWRTracker

admin.site.register(AWRConfig)
admin.site.register(AWRTracker)
