from django.urls import include, path

urlpatterns = [
    path("", include("interview.rest.urls.interview")),
    path("conversations/", include("interview.rest.urls.conversations")),
    path("call/config/", include("interview.rest.urls.config")),
]
