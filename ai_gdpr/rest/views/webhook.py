from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ai_gdpr.tasks import process_candidate_email_response


@csrf_exempt
@require_http_methods(["POST"])
def gdpr_email_webhook_sendgrid(request):
    """
    Webhook endpoint specifically for SendGrid Inbound Parse

    SendGrid sends data as form-encoded, not JSON
    """
    try:
        candidate_email = request.POST.get("from")
        subject = request.POST.get("subject", "")
        message_body = request.POST.get("text") or request.POST.get("html", "")
        if not candidate_email:
            return JsonResponse({"error": "Missing sender email address"}, status=400)

        if not message_body:
            return JsonResponse({"error": "Missing email message body"}, status=400)
        from ai_gdpr.tasks import extract_org_id_from_subject

        organization_id = extract_org_id_from_subject(subject)

        if not organization_id:
            return JsonResponse(
                {
                    "error": "Could not extract organization ID from subject",
                    "subject": subject,
                },
                status=400,
            )
        process_candidate_email_response.delay(
            email=candidate_email,
            candidate_message=message_body.strip(),
            organization_id=organization_id,
            subject=subject,
        )

        return JsonResponse(
            {"status": "success", "message": "Email response queued for processing"},
            status=200,
        )

    except Exception as e:
        return JsonResponse({"error": f"Internal server error: {str(e)}"}, status=500)
