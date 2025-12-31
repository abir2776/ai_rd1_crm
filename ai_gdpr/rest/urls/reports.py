from django.urls import path

from ai_gdpr.rest.views.reports import GDPRReportListView

urlpatterns = [path("", GDPRReportListView.as_view(), name="gdpr-report-list")]
