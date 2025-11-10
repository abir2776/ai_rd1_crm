# interview/urls.py
from django.urls import path

from interview.rest.views.config import (
    AIPhoneCallConfigDetailView,
    AIPhoneCallConfigListCreateView,
)

urlpatterns = [
    path(
        "",
        AIPhoneCallConfigListCreateView.as_view(),
        name="aiphonecallconfig-list-create",
    ),
    path(
        "<uuid:uid>",
        AIPhoneCallConfigDetailView.as_view(),
        name="aiphonecallconfig-detail",
    ),
]
