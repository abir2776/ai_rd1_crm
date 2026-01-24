from django.urls import path

from ai_gdpr.rest.views.webhook import (
    gdpr_email_webhook_sendgrid,
)

urlpatterns = [
    path(
        "",
        gdpr_email_webhook_sendgrid,
        name="gdpr_email_webhook_sendgrid",
    ),
]
