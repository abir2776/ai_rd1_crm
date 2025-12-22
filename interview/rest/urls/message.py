# urls.py
from django.urls import path

from interview.rest.views.message import twilio_sms_webhook, twilio_whatsapp_webhook

urlpatterns = [
    path("webhooks/twilio/sms", twilio_sms_webhook, name="twilio_sms_webhook"),
    path(
        "webhooks/twilio/whatsapp",
        twilio_whatsapp_webhook,
        name="twilio_whatsapp_webhook",
    ),
]
