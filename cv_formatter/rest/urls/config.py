from django.urls import path

from cv_formatter.rest.views.config import (
    CVFormatterConfigDetailView,
    CVFormatterConfigListCreateView,
)

urlpatterns = [
    path(
        "", CVFormatterConfigListCreateView.as_view(), name="cv-formatter-list-create"
    ),
    path(
        "details",
        CVFormatterConfigDetailView.as_view(),
        name="cv-formatter-config-details",
    ),
]
