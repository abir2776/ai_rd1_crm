from django.urls import path

from ai_lead_generation.rest.views.reports import (
    CandidateLeadReportListView,
    OpportunitiesReportListView,
)

urlpatterns = [
    path(
        "lead-generation",
        CandidateLeadReportListView.as_view(),
        name="candidate-lead-generation-report",
    ),
    path(
        "opportunity",
        OpportunitiesReportListView.as_view(),
        name="opportunities-created-report",
    ),
]
