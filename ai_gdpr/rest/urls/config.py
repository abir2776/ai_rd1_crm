from django.urls import path

from ai_gdpr.rest.views.config import (
    GDPREmailConfigDetailView,
    GDPREmailConfigListCreateView,
)

urlpatterns = [
    path("", GDPREmailConfigListCreateView.as_view(), name="gdpr-email-config"),
    path(
        "details", GDPREmailConfigDetailView.as_view(), name="gdpr-email-config-details"
    ),
]
