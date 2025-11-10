from django.urls import path

from ..views.interview import InterviewTakenCreateView, InterviewTakenListView

urlpatterns = [
    path("save/", InterviewTakenCreateView.as_view(), name="save_interview"),
    path("", InterviewTakenListView.as_view(), name="interview-list"),
]
