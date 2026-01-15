from django.urls import path

from cv_formatter.rest.views.reports import RepostListAPIView

urlpatterns = [path("", RepostListAPIView.as_view(), name="formatted_cv_report-list")]
