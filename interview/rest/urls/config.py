# interview/urls.py
from django.urls import path

from interview.rest.views.config import (
    AIPhoneCallConfigDetailView,
    AIPhoneCallConfigListCreateView,
    PrimaryQuestionListView,
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
    path(
        "primary_questions",
        PrimaryQuestionListView.as_view(),
        name="primary-question-list",
    ),
]
