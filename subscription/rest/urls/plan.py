from django.urls import path
from subscription.rest.views.plan import PlanFeatureListView

urlpatterns = [
    path(
        "<uuid:feature_uid>/",
        PlanFeatureListView.as_view(),
        name="subscription-plan-list",
    ),
]
