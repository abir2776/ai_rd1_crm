from django.urls import path

from interview.rest.views.client_call_test import (
    CallRequestCreateView,
    MeetingBookingAPIView,
)

urlpatterns = [
    path("", CallRequestCreateView.as_view(), name="client-call-test"),
    path("bookings", MeetingBookingAPIView.as_view(), name="client-bookings"),
]
