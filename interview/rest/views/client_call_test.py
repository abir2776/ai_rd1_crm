# calls/views.py
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from interview.models import CallRequest
from interview.rest.serializers.client_call_test import CallRequestSerializer
from interview.tasks.ai_phone import initiate_call
from interview.utils import can_place_call, local_to_utc


class CallRequestCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = CallRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        phone = data["phone"]

        if not can_place_call(phone):
            raise ValidationError(
                {
                    "detail": (
                        "You can place a maximum of 2 call requests "
                        "within 12 hours. Please try again later."
                    )
                }
            )

        scheduled_at_utc = None

        if data["call_type"] == CallRequest.CALL_SCHEDULE:
            scheduled_at_utc = local_to_utc(
                data["scheduled_at"],
                data.get("timezone", "UTC"),
            )

        call_request = CallRequest.objects.create(
            name=data["name"],
            phone=phone,
            call_type=data["call_type"],
            scheduled_at=scheduled_at_utc,
            timezone=data.get("timezone", "UTC"),
        )

        if call_request.call_type == CallRequest.CALL_NOW:
            initiate_call.delay(call_request.id)
        else:
            initiate_call.apply_async(
                args=[call_request.id],
                eta=scheduled_at_utc,
            )

        return Response(
            {
                "message": "Call request created successfully",
                "call_id": call_request.id,
            },
            status=status.HTTP_201_CREATED,
        )
