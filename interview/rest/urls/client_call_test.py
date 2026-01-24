from django.urls import path

from interview.rest.views.client_call_test import (
    CallRequestCreateView,
    MeetingBookingAPIView,
    send_client_interest_email
)

urlpatterns = [
    path("", CallRequestCreateView.as_view(), name="client-call-test"),
    path("bookings", MeetingBookingAPIView.as_view(), name="client-bookings"),
    path("email",send_client_interest_email, name='client_interest_email')
]
