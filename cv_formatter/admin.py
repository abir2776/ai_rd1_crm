from django.contrib import admin

from .models import CVFormatterConfig, FormattedCV

admin.site.register(CVFormatterConfig)
admin.site.register(FormattedCV)
