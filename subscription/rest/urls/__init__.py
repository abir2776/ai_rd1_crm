from django.urls import include, path

urlpatterns = [
    path("features/", include("subscription.rest.urls.feature")),
    path("plan/", include("subscription.rest.urls.plan")),
]
