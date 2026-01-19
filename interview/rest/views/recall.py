# views.py
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from interview.models import AIPhoneCallConfig, InterviewTaken
from interview.tasks import make_interview_call


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def retry_disconnected_candidate(request, interview_id):
    try:
        interview = get_object_or_404(
            InterviewTaken,
            uid=interview_id,
            organization=request.user.get_organization(),
        )
        if interview.ai_decision not in ["user_disconnect", "network_disconnect"]:
            return Response(
                {
                    "error": "This candidate was not disconnected",
                    "ai_decision": interview.ai_decision,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            config = AIPhoneCallConfig.objects.get(
                organization_id=interview.organization_id
            )
        except AIPhoneCallConfig.DoesNotExist:
            return Response(
                {"error": "No call configuration found for this organization"},
                status=status.HTTP_404_NOT_FOUND,
            )
        candidate_phone = interview.candidate_phone
        if candidate_phone and not candidate_phone.startswith("+"):
            if candidate_phone.startswith("0"):
                candidate_phone = f"+44{candidate_phone[1:]}"
            elif candidate_phone.startswith("44"):
                candidate_phone = f"+{candidate_phone}"
            else:
                candidate_phone = f"+{candidate_phone}"
        primary_questions = config.get_primary_questions()
        from interview.tasks import generate_welcome_audio
        welcome_text = (
            f"Welcome to the {interview.organization.name} Platform and thank you for your "
            f"application for the {interview.job_title} position. May I talk with you for "
            f"some moments please?"
        )

        welcome_audio_url, welcome_text = generate_welcome_audio(
            welcome_text=welcome_text,
            voice_id=config.voice_id,
        )
        make_interview_call.delay(
            to_number=candidate_phone,
            from_phone_number=str(config.phone.phone_number),
            organization_id=interview.organization_id,
            application_id=interview.application_id,
            interview_type="general",
            candidate_name=interview.candidate_name,
            candidate_id=interview.candidate_id,
            job_title=interview.job_title,
            job_ad_id=interview.job_id,
            job_details=interview.job_details,
            primary_questions=primary_questions,
            should_end_if_primary_question_failed=config.end_call_if_primary_answer_negative,
            welcome_message_audio_url=welcome_audio_url,
            welcome_text=welcome_text,
            voice_id=config.voice_id,
            candidate_email=interview.candidate_email,
            is_retry=True,
        )

        return Response(
            {
                "message": "Call retry initiated successfully",
                "candidate_name": interview.candidate_name,
                "candidate_phone": candidate_phone,
                "job_title": interview.job_title,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {"error": f"Failed to retry call: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def retry_all_disconnected_candidates(request):
    organization_id = request.user.get_organization().id
    job_id = request.query_params.get("job_id")
    retry_limit = int(request.query_params.get("limit", 10))
    try:
        try:
            config = AIPhoneCallConfig.objects.get(organization_id=organization_id)
        except AIPhoneCallConfig.DoesNotExist:
            return Response(
                {"error": "No call configuration found for this organization"},
                status=status.HTTP_404_NOT_FOUND,
            )
        disconnected_interviews = InterviewTaken.objects.filter(
            organization_id=organization_id,
            ai_decision__in=["user_disconnect", "network_disconnect"],
        )

        if job_id:
            disconnected_interviews = disconnected_interviews.filter(job_id=job_id)

        disconnected_interviews = disconnected_interviews[:retry_limit]

        if not disconnected_interviews.exists():
            return Response(
                {"message": "No disconnected candidates found"},
                status=status.HTTP_200_OK,
            )

        retried_count = 0
        failed_retries = []

        for i, interview in enumerate(disconnected_interviews):
            try:
                candidate_phone = interview.candidate_phone
                if candidate_phone and not candidate_phone.startswith("+"):
                    if candidate_phone.startswith("0"):
                        candidate_phone = f"+44{candidate_phone[1:]}"
                    elif candidate_phone.startswith("44"):
                        candidate_phone = f"+{candidate_phone}"
                    else:
                        candidate_phone = f"+{candidate_phone}"
                primary_questions = config.get_primary_questions()
                from interview.tasks import generate_welcome_audio
                welcome_text = (
                    f"Welcome to the {interview.organization.name} Platform and thank you for your "
                    f"application for the {interview.job_title} position. May I talk with you for "
                    f"some moments please?"
                )
                welcome_audio_url, welcome_text = generate_welcome_audio(
                    welcome_text=welcome_text,
                    voice_id=config.voice_id,
                )
                countdown = i * 120

                make_interview_call.apply_async(
                    args=[
                        candidate_phone,
                        str(config.phone.phone_number),
                        interview.organization_id,
                        interview.application_id,
                        "general",
                        interview.candidate_name,
                        interview.candidate_id,
                        interview.job_title,
                        interview.job_id,
                        interview.job_details,
                        primary_questions,
                        config.end_call_if_primary_answer_negative,
                        welcome_audio_url,
                        welcome_text,
                        config.voice_id,
                        interview.candidate_email,
                        True,
                    ],
                    countdown=countdown,
                )
                retried_count += 1

            except Exception as e:
                failed_retries.append(
                    {"candidate_name": interview.candidate_name, "error": str(e)}
                )

        response_data = {
            "message": f"Retry initiated for {retried_count} disconnected candidates",
            "retried_count": retried_count,
            "total_disconnected": disconnected_interviews.count(),
        }

        if failed_retries:
            response_data["failed_retries"] = failed_retries

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {"error": f"Failed to retry calls: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
