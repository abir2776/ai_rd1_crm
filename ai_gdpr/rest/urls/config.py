from django.urls import path

from ai_gdpr.rest.views.config import GDPREmailConfigListCreateView

urlpatterns = [
    path("", GDPREmailConfigListCreateView.as_view(), name="gdpr-email-config"),
]
