from django.urls import path

from subscription.rest.views.feature import FeatureListView

urlpatterns = [path("", FeatureListView.as_view(), name="feature-list")]
