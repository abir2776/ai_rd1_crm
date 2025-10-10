from django.contrib import admin
from .models import Organization, Platform, OrganizationPlatform, OrganizationUser

# Register your models here.
admin.site.register(Organization)
admin.site.register(Platform)
admin.site.register(OrganizationPlatform)
admin.site.register(OrganizationUser)
