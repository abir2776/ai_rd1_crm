import os
import time
import uuid
from datetime import datetime, timezone

import requests
from celery import shared_task
from django.core.files.base import ContentFile
from dotenv import load_dotenv

from interview.models import AIPhoneCallConfig, InterviewTaken
from organizations.models import Organization
from subscription.models import Subscription

load_dotenv()

BASE_API_URL = os.getenv("CALLING_BASE_URL", "http://localhost:5050")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"


def generate_welcome_audio(
    organization_name: str, job_title: str, voice_id: str
) -> str:
    """
    Generate welcome message audio using ElevenLabs TTS.
    Returns the URL of the saved audio file.
    """
    welcome_text = (
        f"Welcome to the {organization_name} Platform and thank you for your "
        f"application for the {job_title} position. May I talk with you for "
        f"some moments please?"
    )

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": ELEVENLABS_API_KEY,
    }

    payload = {
        "text": welcome_text,
        "model_id": "eleven_v3",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.5,
        },
    }

    try:
        response = requests.post(
            f"{ELEVENLABS_API_URL}/{voice_id}",
            json=payload,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()

        # Save the audio file
        filename = f"welcome_messages/{uuid.uuid4()}.mp3"

        # Using Django's default storage
        from django.core.files.storage import default_storage

        file_path = default_storage.save(filename, ContentFile(response.content))
        audio_url = default_storage.url(file_path)

        # If using S3 or similar, this returns full URL
        # If using local storage, you may need to prepend your domain
        if not audio_url.startswith("http"):
            audio_url = f"{audio_url}"

        print(f"Generated welcome audio: {audio_url}")
        return audio_url, welcome_text

    except requests.RequestException as e:
        print(f"Error generating welcome audio: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected error generating welcome audio: {str(e)}")
        return None


@shared_task(max_retries=3)
def make_interview_call(
    to_number: str,
    from_phone_number: str,
    organization_id: int,
    application_id: int,
    interview_type: str = "general",
    candidate_name: str = None,
    candidate_id: int = None,
    job_title: str = None,
    job_ad_id: int = None,
    job_details: dict = None,
    primary_questions: list = [],
    should_end_if_primary_question_failed: bool = False,
    welcome_message_audio_url: str = None,
    welcome_text: str = None,
    voice_id: str = "SQ1QAX1hsTZ1d6O0dCWA",
    candidate_email: str = None,
):
    try:
        payload = {
            "to_phone_number": to_number,
            "from_phone_number": from_phone_number,
            "organization_id": organization_id,
            "application_id": application_id,
            "candidate_id": candidate_id,
            "job_title": job_title,
            "job_id": job_ad_id,
            "job_details": job_details or {},
            "candidate_first_name": candidate_name,
            "interview_type": interview_type,
            "primary_questions": primary_questions,
            "should_end_if_primary_question_failed": should_end_if_primary_question_failed,
            "welcome_message_audio_url": welcome_message_audio_url,
            "welcome_text": welcome_text,
            "voice_id": voice_id,
            "candidate_email": candidate_email,
        }

        response = requests.post(
            f"{BASE_API_URL}/initiate-call",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        print("Call initiated successfully")
        # update_application_status_after_call(organization_id, application_id)

    except Exception as exc:
        print(f"Error making call to {to_number}: {str(exc)}")


def fetch_job_details(job_self_url: str, config):
    access_token = config.platform.access_token
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(job_self_url, headers=headers, timeout=30)
        if response.status_code == 401:
            print("Access token expired, refreshing...")
            access_token = config.platform.refresh_access_token()
            if not access_token:
                print("Error: Could not refresh access token")
                return {}

            headers["Authorization"] = f"Bearer {access_token}"
            response = requests.get(job_self_url, headers=headers, timeout=30)
        response.raise_for_status()
        job_data = response.json()

        return {
            "description": job_data.get("description", ""),
            "summary": job_data.get("summary", ""),
            "location": job_data.get("location", {}).get("city", ""),
            "salary": job_data.get("salary", {}).get("description", ""),
        }
    except Exception as e:
        print(f"Error fetching job details from {job_self_url}: {str(e)}")
        return {
            "description": "",
            "summary": "",
            "location": "",
            "salary": "",
        }


def update_application_status_after_call(organization_id: int, application_id: int):
    try:
        config = AIPhoneCallConfig.objects.get(organization_id=organization_id)
        status_id = getattr(config, "status_when_call_is_placed", None)

        if not status_id:
            print(
                f"No status_when_call_is_placed configured for organization {organization_id}"
            )
            return

        jobadder_api_url = f"{config.platform.base_url}/applications/{application_id}"

        access_token = config.platform.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        payload = {"statusId": status_id}

        response = requests.put(
            jobadder_api_url, json=payload, headers=headers, timeout=10
        )

        if response.status_code == 401:
            print("Access token expired, refreshing...")
            access_token = config.platform.refresh_access_token()
            if not access_token:
                print("Error: Could not refresh access token")
                return

            headers["Authorization"] = f"Bearer {access_token}"
            response = requests.put(
                jobadder_api_url, json=payload, headers=headers, timeout=10
            )

        response.raise_for_status()
        print(
            f"Successfully updated application {application_id} status to {status_id}"
        )

    except AIPhoneCallConfig.DoesNotExist:
        print(f"No config found for organization {organization_id}")
    except requests.RequestException as e:
        print(f"Failed to update JobAdder application status: {str(e)}")
    except Exception as e:
        print(f"Unexpected error updating application status: {str(e)}")


def has_enough_time_passed(updated_at_str: str, waiting_duration_minutes: int) -> bool:
    try:
        updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
        current_time = datetime.now(timezone.utc)
        time_diff = (current_time - updated_at).total_seconds() / 60
        return time_diff >= waiting_duration_minutes
    except Exception as e:
        print(f"Error parsing updatedAt timestamp '{updated_at_str}': {str(e)}")
        return False


@shared_task
def fetch_platform_candidates(config):
    access_token = config.platform.access_token
    primary_questions = config.get_primary_questions()
    waiting_duration = config.calling_time_after_status_update
    organization_name = config.organization.name  # Get organization name

    if not access_token:
        print("Error: Could not get JobAdder access token")
        return []

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    candidates = []

    try:
        jobs_response = requests.get(
            f"{config.platform.base_url}/jobads",
            headers=headers,
            timeout=30,
        )
        if jobs_response.status_code == 401:
            print("Access token expired, refreshing...")
            access_token = config.platform.refresh_access_token()
            if not access_token:
                print("Error: Could not refresh access token")
                return []

            headers["Authorization"] = f"Bearer {access_token}"
            jobs_response = requests.get(
                f"{config.platform.base_url}/jobads",
                headers=headers,
                timeout=30,
            )

        jobs_response.raise_for_status()
        jobs_data = jobs_response.json()

        print(f"Found {len(jobs_data.get('items', []))} live jobs")
        for job in jobs_data.get("items", []):
            time.sleep(0.5)
            if job.get("state") == config.jobad_status_for_calling:
                ad_id = job.get("adId")
                job_title = job.get("title")
                job_self_url = job.get("links", {}).get("self")
                applications_url = job.get("links", {}).get("applications")
                if not applications_url:
                    print(f"No applications link found for job: {job_title}")
                    continue
                job_details = fetch_job_details(job_self_url, config)

                # Generate welcome audio for this job
                welcome_audio_url, welcome_text = generate_welcome_audio(
                    organization_name=organization_name,
                    job_title=job_title,
                    voice_id=config.voice_id,
                )

                try:
                    applications_response = requests.get(
                        applications_url,
                        headers=headers,
                        timeout=30,
                    )
                    if applications_response.status_code == 401:
                        access_token = config.platform.refresh_access_token()
                        if access_token:
                            headers["Authorization"] = f"Bearer {access_token}"
                            applications_response = requests.get(
                                applications_url,
                                headers=headers,
                                timeout=30,
                            )

                    applications_response.raise_for_status()
                    applications_data = applications_response.json()

                    for application in applications_data.get("items", []):
                        application_id = application.get("applicationId")
                        candidate = application.get("candidate", {})
                        candidate_id = candidate.get("candidateId")
                        candidate_first_name = candidate.get("firstName", "")
                        candidate_last_name = candidate.get("lastName", "")
                        candidate_email = candidate.get("email", "")
                        candidate_phone = candidate.get("mobile", "")
                        updated_at = application.get("updatedAt", "")
                        status = application.get("status")

                        if candidate_phone and not candidate_phone.startswith("+"):
                            if candidate_phone.startswith("0"):
                                candidate_phone = f"+44{candidate_phone[1:]}"
                            elif candidate_phone.startswith("44"):
                                candidate_phone = f"+{candidate_phone}"
                            else:
                                candidate_phone = f"+{candidate_phone}"

                        if (
                            status.get("statusId")
                            == config.application_status_for_calling
                            and has_enough_time_passed(updated_at, waiting_duration)
                            and candidate_id == 16995516
                        ):
                            candidate_data = {
                                "to_number": candidate_phone,
                                "from_phone_number": str(config.phone.phone_number),
                                "organization_id": config.organization_id,
                                "application_id": application_id,
                                "candidate_id": candidate_id,
                                "candidate_name": f"{candidate_first_name} {candidate_last_name}",
                                "candidate_email": candidate_email,
                                "job_title": job_title,
                                "job_ad_id": ad_id,
                                "job_details": job_details,
                                "interview_type": "general",
                                "primary_questions": primary_questions,
                                "should_end_if_primary_question_failed": config.end_call_if_primary_answer_negative,
                                "welcome_message_audio_url": welcome_audio_url,
                                "welcome_text": welcome_text,
                                "voice_id": config.voice_id,
                            }

                            candidates.append(candidate_data)
                            print(
                                f"Added candidate: {candidate_first_name} {candidate_last_name} for job: {job_title}"
                            )
                        elif (
                            job.get("state") == config.jobad_status_for_calling
                            and application.get("statusId")
                            == config.application_status_for_calling
                        ):
                            print(
                                f"Skipped candidate: {candidate_first_name} {candidate_last_name} - "
                                f"waiting period not elapsed (updated: {updated_at})"
                            )

                except Exception as e:
                    print(f"Error fetching applications for job {job_title}: {str(e)}")
                    continue

        print(f"Total candidates collected: {len(candidates)}")
        return candidates

    except Exception as e:
        print(f"Error fetching JobAdder data: {str(e)}")
        return []


@shared_task
def bulk_interview_calls(organization_id: int = None):
    try:
        config = AIPhoneCallConfig.objects.get(organization_id=organization_id)
    except:
        print(f"No call configuration found for organization_{organization_id}")
        return
    candidates = fetch_platform_candidates(config)

    if not candidates:
        return {"error": "No candidates provided or fetched"}

    for i, candidate in enumerate(candidates):
        countdown = i * 120
        is_taken = InterviewTaken.objects.filter(
            organization_id=organization_id,
            candidate_id=candidate.get("candidate_id"),
            application_id=candidate["application_id"],
        ).exists()
        if not is_taken:
            make_interview_call.apply_async(
                args=[
                    candidate["to_number"],
                    candidate["from_phone_number"],
                    candidate["organization_id"],
                    candidate["application_id"],
                    candidate.get("interview_type", "general"),
                    candidate.get("candidate_name"),
                    candidate.get("candidate_id"),
                    candidate.get("job_title"),
                    candidate.get("job_ad_id"),
                    candidate.get("job_details"),
                    candidate.get("primary_questions"),
                    candidate.get("should_end_if_primary_question_failed"),
                    candidate.get("welcome_message_audio_url"),
                    candidate.get("welcome_text"),
                    candidate.get("voice_id"),
                    candidate.get("candidate_email"),
                ],
                countdown=countdown,
            )


@shared_task
def initiate_all_interview():
    organization_ids = Organization.objects.filter().values_list("id", flat=True)
    subscribed_organization_ids = Subscription.objects.filter(
        organization_id__in=organization_ids, available_limit__gt=0
    ).values_list("organization_id", flat=True)
    for organization_id in subscribed_organization_ids:
        print(f"Initiated bulk interview call for organization_{organization_id}")
        bulk_interview_calls.delay(organization_id)
