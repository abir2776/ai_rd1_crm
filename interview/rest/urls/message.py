# urls.py
from django.urls import path
from interview.rest.views.message import twilio_sms_webhook

urlpatterns = [
    path("webhooks/twilio/sms", twilio_sms_webhook, name="twilio_sms_webhook"),
]
