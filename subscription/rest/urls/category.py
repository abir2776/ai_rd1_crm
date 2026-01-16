from django.urls import path

from subscription.rest.views.category import CategoryListView

urlpatterns = [path("", CategoryListView.as_view(), name="subscription-category-list")]
