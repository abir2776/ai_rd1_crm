from django.urls import path

from interview.rest.views import recall

urlpatterns = [
    path(
        "<str:interview_id>",
        recall.retry_disconnected_candidate,
        name="retry-disconnected-candidate",
    ),
    path(
        "",
        recall.retry_all_disconnected_candidates,
        name="retry-all-disconnected-candidates",
    ),
]
