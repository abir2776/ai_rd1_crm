from django.urls import path

from cv_formatter.rest.views.config import CVFormatterConfigListCreateView

urlpatterns = [
    path("", CVFormatterConfigListCreateView.as_view(), name="cv-formatter-list-create")
]
