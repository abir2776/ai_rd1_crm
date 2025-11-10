from django.urls import path

from subscription.rest.views.plan import SubscriptionPlanListView

urlpatterns = [
    path("", SubscriptionPlanListView.as_view(), name="subscription-plan-list")
]
