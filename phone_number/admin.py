from django.contrib import admin

from .models import (
    RegulatoryAddress,
    RegulatoryBundle,
    SupportingDocument,
    TwilioPhoneNumber,
    TwilioSubAccount,
)

admin.site.register(TwilioSubAccount)
admin.site.register(RegulatoryBundle)
admin.site.register(RegulatoryAddress)
admin.site.register(SupportingDocument)
admin.site.register(TwilioPhoneNumber)

# Register your models here.
