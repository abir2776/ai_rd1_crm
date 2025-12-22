from django.urls import path

from interview.rest.views.messageconfig import (
    AIMessageConfigDetailView,
    AIMessageConfigListCreateView,
)

urlpatterns = [
    path(
        "",
        AIMessageConfigListCreateView.as_view(),
        name="aimessageconfig-list-create",
    ),
    path(
        "<uuid:uid>",
        AIMessageConfigDetailView.as_view(),
        name="aimessageconfig-detail",
    ),
]
