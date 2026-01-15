from django.urls import path

from ..views import list

urlpatterns = [
    path(
        "status",
        list.jobadder_placement_status_list,
        name="jobadder-placement-status-list",
    ),
    path(
        "payment-types",
        list.jobadder_payment_types_list,
        name="jobadder-payment-types-list",
    ),
]
