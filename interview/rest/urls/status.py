from django.urls import path

from ..views.status import jobadder_status_list

urlpatterns = [
    path("", jobadder_status_list, name="jobadder-status-list")
]
