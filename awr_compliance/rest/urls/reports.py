from django.urls import path

from awr_compliance.rest.views.reports import AWRReportListView

urlpatterns = [path("", AWRReportListView.as_view(), name="awr-report-list")]
