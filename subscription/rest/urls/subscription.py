from django.urls import path

from subscription.rest.views.subscription import SubscriptionListCreateView

urlpatterns = [
    path("", SubscriptionListCreateView.as_view(), name="subscription-list-create")
]
