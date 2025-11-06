from django.urls import path, include

urlpatterns = [path("conversations/", include("interview.rest.urls.conversations"))]
