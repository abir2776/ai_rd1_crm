from django.urls import path

from ai_skill_search.rest.views.list import jobadder_candidate_status_list

urlpatterns = [
    path(
        "candidates/status",
        jobadder_candidate_status_list,
        name="candidate-status-list",
    )
]
