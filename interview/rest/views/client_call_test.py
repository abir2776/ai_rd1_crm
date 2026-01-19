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
from rest_framework.decorators import api_view, permission_classes
from datetime import datetime
from common.tasks import send_email_task


class CallRequestCreateView(APIView):
    permission_classes = [AllowAny]
    # throttle_classes = [CallRequestIPThrottle]

    def post(self, request):
        serializer = CallRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        phone = data["phone"]
        if phone.startswith("+440"):
            phone = "+44" + phone[4:]

        twelve_hours_ago = timezone.now() - timedelta(hours=12)

        call_count = CallRequest.objects.filter(
            phone=phone,
            created_at__gte=twelve_hours_ago,
        ).count()

        if call_count >= 2 and phone != "+447872603687":
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
            schedule_call = CallRequest.objects.filter(
                phone=phone, call_type="SCHEDULE", is_called=False
            )
            if schedule_call.exists() and phone != "+447872603687":
                raise ValidationError(
                    {
                        "detail": (
                            "You already have incomplete schedule call. "
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


@api_view(['POST'])
@permission_classes([AllowAny])
def send_client_interest_email(request):
    try:
        required_fields = [
            'call_request_id',
            'client_name', 
            'client_phone',
            'client_company_name',
            'client_company_size',
            'inbound_calls_per_day'
        ]
        
        missing_fields = [field for field in required_fields if field not in request.data]
        if missing_fields:
            return Response(
                {
                    'error': 'Missing required fields',
                    'missing_fields': missing_fields
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        client_name = request.data['client_name']
        client_phone = request.data['client_phone']
        client_company_name = request.data['client_company_name']
        client_company_size = request.data['client_company_size']
        inbound_calls_per_day = request.data['inbound_calls_per_day']
        call_request_id = request.data['call_request_id']
        context = {
            'client_name': client_name,
            'client_phone': client_phone,
            'client_company_name': client_company_name,
            'client_company_size': client_company_size,
            'inbound_calls_per_day': inbound_calls_per_day,
            'call_request_id': call_request_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        subject = f'🎉 New Client Interest: {client_name} from {client_company_name}'
        send_email_task.delay(
            subject=subject,
            recipient='steven@rd1.co.uk',
            template_name='emails/client_interest_notification.html',
            context=context,
            customer_email=None,
            reply_to=None
        )
        
        return Response(
            {
                'status': 'success',
                'message': 'Email notification sent successfully',
                'client_name': client_name,
                'company': client_company_name
            },
            status=status.HTTP_200_OK
        )
        
    except Exception as e:
        return Response(
            {
                'status': 'error',
                'message': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
