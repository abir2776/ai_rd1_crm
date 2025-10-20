from django.urls import path, include

urlpatterns = [
    path("/phone-numbers", include("core.rest.urls.phone_numbers")),
]
