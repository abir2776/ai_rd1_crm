from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from twilio.twiml.messaging_response import MessagingResponse

from interview.tasks.ai_sms import process_candidate_sms_response


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
