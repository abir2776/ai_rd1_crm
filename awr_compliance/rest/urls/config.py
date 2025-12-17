from django.urls import path

from awr_compliance.rest.views.config import AWRConfigListCreateView

urlpatterns = [
    path("", AWRConfigListCreateView.as_view(), name="awr-email-config"),
]
