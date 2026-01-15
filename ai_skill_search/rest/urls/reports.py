from django.urls import path

from ai_skill_search.rest.views.reports import CandidateSkillMatchReportListView

urlpatterns = [
    path(
        "",
        CandidateSkillMatchReportListView.as_view(),
        name="candidate-skill-search-report",
    )
]
