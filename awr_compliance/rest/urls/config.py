from django.urls import path

from awr_compliance.rest.views.config import (
    AWRConfigDetailView,
    AWRConfigListCreateView,
)

urlpatterns = [
    path("", AWRConfigListCreateView.as_view(), name="awr-email-config"),
    path("details", AWRConfigDetailView.as_view(), name="awr-config-detils"),
]
