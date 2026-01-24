from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from twilio.twiml.messaging_response import MessagingResponse

from interview.models import InterviewMessageConversation
from interview.rest.serializers.message import MessageInterviewReportSerializer
from interview.tasks.ai_sms import process_candidate_sms_response
from interview.tasks.ai_whatsapp import process_candidate_whatsapp_response
from whatsapp_campaign.tasks import process_campaign_response


@csrf_exempt
@require_POST
def twilio_sms_webhook(request):
    try:
        from_number = request.POST.get("From", "")
        message_body = request.POST.get("Body", "")
        normalized_from = from_number.replace(" ", "").replace("-", "")
        if normalized_from and not normalized_from.startswith("+"):
            normalized_from = f"+{normalized_from}"

        print(f"Received SMS from {from_number}: {message_body}")
        process_candidate_sms_response.delay(
            candidate_phone=normalized_from,
            candidate_message=message_body,
        )

        print(f"Queued SMS processing for candidate {normalized_from}")

        response = MessagingResponse()

        return HttpResponse(str(response), content_type="text/xml")

    except Exception as e:
        print(f"Error in Twilio webhook: {str(e)}")
        response = MessagingResponse()
        return HttpResponse(str(response), content_type="text/xml")


@csrf_exempt
@require_POST
def twilio_whatsapp_webhook(request):
    try:
        from_number = request.POST.get("From", "")
        message_body = request.POST.get("Body", "")

        if from_number.startswith("whatsapp:"):
            from_number = from_number.replace("whatsapp:", "")
        normalized_from = from_number.replace(" ", "").replace("-", "")
        if normalized_from and not normalized_from.startswith("+"):
            normalized_from = f"+{normalized_from}"

        print(f"Received WhatsApp message from {from_number}: {message_body}")
        process_candidate_whatsapp_response.delay(
            candidate_phone=normalized_from,
            candidate_message=message_body,
        )
        process_campaign_response.delay(
            contact_phone=normalized_from, contact_message=message_body
        )

        print(f"Queued WhatsApp processing for candidate {normalized_from}")
        response = MessagingResponse()
        return HttpResponse(str(response), content_type="text/xml")

    except Exception as e:
        print(f"Error in Twilio WhatsApp webhook: {str(e)}")
        response = MessagingResponse()
        return HttpResponse(str(response), content_type="text/xml")


class MessageInterviewReport(generics.ListAPIView):
    serializer_class = MessageInterviewReportSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["type"]

    def get_queryset(self):
        organization = self.request.user.get_organization()
        return InterviewMessageConversation.objects.filter(organization=organization)
