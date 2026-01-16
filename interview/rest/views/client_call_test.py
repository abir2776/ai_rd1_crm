from datetime import timedelta

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from interview.models import CallRequest, MeetingBooking
from interview.rest.serializers.client_call_test import (
    CallRequestSerializer,
    MeetingBookingSerializer,
)
from interview.tasks.ai_phone import initiate_call
from interview.throttles import CallRequestIPThrottle


class CallRequestCreateView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [CallRequestIPThrottle]

    def post(self, request):
        serializer = CallRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        phone = data["phone"]

        twelve_hours_ago = timezone.now() - timedelta(hours=12)

        call_count = CallRequest.objects.filter(
            phone=phone,
            created_at__gte=twelve_hours_ago,
        ).count()

        if call_count >= 2:
            raise ValidationError(
                {
                    "detail": (
                        "You can place a maximum of 2 call requests "
                        "within 12 hours. Please try again later."
                    )
                }
            )

        scheduled_at = None
        if data["call_type"] == "SCHEDULE":
            scheduled_at = data["scheduled_at"]
            schedule_call = CallRequest.objects.filter(phone=phone,call_type="SCHEDULE",is_called=False)
            if schedule_call.exists:
                raise ValidationError(
                    {
                        "detail": (
                            "You already have incomplete schedule call."
                            "Please try again later after completing already scheduled call."
                        )
                    }
                )

        call_request = CallRequest.objects.create(
            name=data["name"],
            phone=phone,
            call_type=data["call_type"],
            scheduled_at=scheduled_at,
            company_name=data["company_name"],
            company_size=data["company_size"],
        )

        if call_request.call_type == CallRequest.CALL_NOW:
            initiate_call.delay(call_request.id)
        else:
            initiate_call.apply_async(
                args=[call_request.id],
                eta=scheduled_at,
            )

        return Response(
            {
                "message": "Call request created successfully",
                "call_id": call_request.id,
            },
            status=status.HTTP_201_CREATED,
        )


class MeetingBookingAPIView(ListCreateAPIView):
    serializer_class = MeetingBookingSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "scheduled_at"]
    queryset = MeetingBooking.objects.filter()
