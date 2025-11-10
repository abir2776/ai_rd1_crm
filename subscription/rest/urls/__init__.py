from django.urls import include, path

urlpatterns = [
    path("", include("subscription.rest.urls.subscription")),
    path("features/", include("subscription.rest.urls.feature")),
    path("plan/", include("subscription.rest.urls.plan")),
]
