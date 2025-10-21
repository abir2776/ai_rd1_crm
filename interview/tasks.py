from celery import shared_task
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BASE_API_URL = os.getenv("BASE_URL", "http://localhost:5050")


@shared_task(bind=True, max_retries=3)
def make_interview_call(
    self,
    to_number: str,
    company_id: int,
    application_id: int,
    interview_type: str = "general",
    candidate_name: str = None,
):
    """
    Celery task to make an interview call with company and application tracking.
    Retries up to 3 times if it fails.

    Args:
        to_number: Phone number to call
        company_id: ID of the company (required for Django tracking)
        application_id: ID of the application (required for Django tracking)
        interview_type: Type of interview
        candidate_name: Name of the candidate
    """
    try:
        response = requests.post(
            f"{BASE_API_URL}/initiate-call",
            json={
                "to_number": to_number,
                "interview_type": interview_type,
                "candidate_name": candidate_name,
                "company_id": company_id,
                "application_id": application_id,
            },
            timeout=30,
        )
        response.raise_for_status()

        result = response.json()
        print(f"Call initiated successfully: {result['call_sid']}")
        print(f"Company: {company_id}, Application: {application_id}")
        return result

    except Exception as exc:
        print(f"Error making call to {to_number}: {str(exc)}")
        # Retry after 5 minutes if failed
        raise self.retry(exc=exc, countdown=300)


@shared_task
def schedule_interview_call(
    to_number: str,
    company_id: int,
    application_id: int,
    interview_type: str,
    candidate_name: str,
    scheduled_time: str,
):
    """
    Schedule an interview call for a specific time.

    Args:
        to_number: Phone number to call
        company_id: ID of the company
        application_id: ID of the application
        interview_type: Type of interview
        candidate_name: Name of the candidate
        scheduled_time: ISO format datetime string (e.g., "2025-10-22T10:00:00")
    """
    scheduled_dt = datetime.fromisoformat(scheduled_time)
    eta = scheduled_dt

    make_interview_call.apply_async(
        args=[to_number, company_id, application_id, interview_type, candidate_name],
        eta=eta,
    )

    return f"Interview scheduled for {candidate_name} at {scheduled_time}"


@shared_task
def bulk_interview_calls(candidates: list):
    """
    Make interview calls to multiple candidates.

    Args:
        candidates: List of dicts with keys: to_number, company_id, application_id,
                   interview_type, candidate_name

    Example:
        candidates = [
            {
                "to_number": "+1234567890",
                "company_id": 1,
                "application_id": 100,
                "interview_type": "technical",
                "candidate_name": "John Doe"
            },
            {
                "to_number": "+0987654321",
                "company_id": 1,
                "application_id": 101,
                "interview_type": "general",
                "candidate_name": "Jane Smith"
            }
        ]
    """
    results = []

    for i, candidate in enumerate(candidates):
        # Validate required fields
        if not all(
            k in candidate for k in ["to_number", "company_id", "application_id"]
        ):
            results.append(
                {
                    "candidate": candidate.get("candidate_name", "Unknown"),
                    "status": "failed",
                    "error": "Missing required fields",
                }
            )
            continue

        # Stagger calls by 2 minutes to avoid overwhelming the system
        countdown = i * 120

        task = make_interview_call.apply_async(
            args=[
                candidate["to_number"],
                candidate["company_id"],
                candidate["application_id"],
                candidate.get("interview_type", "general"),
                candidate.get("candidate_name"),
            ],
            countdown=countdown,
        )

        results.append(
            {
                "candidate": candidate.get("candidate_name"),
                "company_id": candidate["company_id"],
                "application_id": candidate["application_id"],
                "task_id": task.id,
                "scheduled_in_seconds": countdown,
                "status": "scheduled",
            }
        )

    return results


@shared_task
def retry_failed_call(
    call_sid: str,
    to_number: str,
    company_id: int,
    application_id: int,
    interview_type: str,
    candidate_name: str,
    max_attempts: int = 3,
):
    """
    Retry a failed interview call with exponential backoff.

    Args:
        call_sid: Original call SID that failed
        to_number: Phone number to call
        company_id: ID of the company
        application_id: ID of the application
        interview_type: Type of interview
        candidate_name: Name of the candidate
        max_attempts: Maximum number of retry attempts
    """
    for attempt in range(max_attempts):
        try:
            response = requests.post(
                f"{BASE_API_URL}/initiate-call",
                json={
                    "to_number": to_number,
                    "interview_type": interview_type,
                    "candidate_name": candidate_name,
                    "company_id": company_id,
                    "application_id": application_id,
                },
                timeout=30,
            )

            if response.status_code == 200:
                return {
                    "success": True,
                    "attempt": attempt + 1,
                    "original_call_sid": call_sid,
                    "new_call_sid": response.json()["call_sid"],
                    "company_id": company_id,
                    "application_id": application_id,
                }

        except Exception as e:
            print(f"Attempt {attempt + 1} failed for call {call_sid}: {str(e)}")
            if attempt < max_attempts - 1:
                # Exponential backoff: 5min, 15min, 45min
                wait_time = 300 * (3**attempt)
                import time

                time.sleep(wait_time)

    return {
        "success": False,
        "attempts": max_attempts,
        "original_call_sid": call_sid,
        "company_id": company_id,
        "application_id": application_id,
    }


# New task for getting interview status from Django
@shared_task
def check_interview_status(interview_uid: str):
    """
    Check the status of an interview from Django

    Args:
        interview_uid: UID of the interview record in Django
    """
    django_api_url = os.getenv("DJANGO_API_URL", "http://localhost:8000")

    try:
        response = requests.get(
            f"{django_api_url}/api/interview/{interview_uid}/", timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error checking interview status: {str(e)}")
        return {"error": str(e)}
