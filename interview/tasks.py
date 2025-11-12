import os

import requests
from celery import shared_task
from dotenv import load_dotenv

from interview.models import AIPhoneCallConfig
from organizations.models import Organization
from subscription.models import Subscription

load_dotenv()

BASE_API_URL = os.getenv("CALLING_BASE_URL", "http://localhost:5050")


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
        }

        response = requests.post(
            f"{BASE_API_URL}/initiate-call",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        print("Call initiated successfully")

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
                return []

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


@shared_task
def fetch_platform_candidates(config):
    access_token = config.platform.access_token
    primary_questions = config.get_primary_questions()

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
            ad_id = job.get("adId")
            job_title = job.get("title")
            job_self_url = job.get("links", {}).get("self")
            applications_url = job.get("links", {}).get("applications")

            if ad_id != 648689:
                continue

            if not applications_url:
                print(f"No applications link found for job: {job_title}")
                continue
            job_details = fetch_job_details(job_self_url, config)

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
                    candidate_phone = candidate.get("mobile", "")
                    if application_id != 10898990:
                        continue

                    candidate_data = {
                        "to_number": candidate_phone,
                        "from_phone_number": str(config.phone.phone_number),
                        "organization_id": config.organization_id,
                        "application_id": application_id,
                        "candidate_id": candidate_id,
                        "candidate_name": candidate_first_name,
                        "job_title": job_title,
                        "job_ad_id": ad_id,
                        "job_details": job_details,
                        "interview_type": "general",
                        "primary_questions": primary_questions,
                        "should_end_if_primary_question_failed": config.end_call_if_primary_answer_negative,
                    }

                    candidates.append(candidate_data)
                    print(
                        f"Added candidate: {candidate_first_name} {candidate_last_name} for job: {job_title}"
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
        bulk_interview_calls.delay(organization_id)
