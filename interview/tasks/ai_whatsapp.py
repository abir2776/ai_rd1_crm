import os
import time
from datetime import datetime, timezone
from typing import Dict, List

import requests
from celery import shared_task
from dotenv import load_dotenv
from openai import OpenAI

from interview.models import (
    AIMessageConfig,
    InterviewMessageConversation,
    ProgressStatus,
    QuestionMessageConfigConnection,
)
from organizations.models import Organization
from phone_number.models import TwilioSubAccount
from subscription.models import Subscription

load_dotenv()

BASE_API_URL = os.getenv("CALLING_BASE_URL", "http://localhost:5050")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


def generate_ai_whatsapp_instructions(
    job_title: str,
    job_id: int,
    application_id: int,
    candidate_name: str,
    job_details: dict,
    primary_questions: List[str] = None,
) -> str:
    """Generate AI instructions for WhatsApp-based interview"""
    instructions = f"""You are an AI recruiter for Recruitment Direct conducting a text-based job interview via WhatsApp. Keep responses conversational but professional, under 300 characters.

## Your Task
You are interviewing {candidate_name} for this position:

Job Details:
- Job Title: {job_title}
- Job ID: {job_id}
- Application ID: {application_id}
"""

    if job_details:
        if job_details.get("summary"):
            instructions += f"- Summary: {job_details['summary']}\n"
        if job_details.get("bulletPoints"):
            bullet_points = job_details["bulletPoints"]
            if isinstance(bullet_points, list):
                instructions += "- Key Points:\n"
                for point in bullet_points:
                    instructions += f"  * {point}\n"
        if job_details.get("location"):
            instructions += f"- Location: {job_details['location']}\n"

    instructions += "\n## Interview Flow\n\n"

    if primary_questions and len(primary_questions) > 0:
        instructions += "### Primary Questions (MUST ASK FIRST)\n\n"
        instructions += "Ask these questions in order:\n\n"
        for idx, question in enumerate(primary_questions, 1):
            instructions += f"{idx}. {question}\n"
        instructions += "\n"

        instructions += """**Primary Question Rules:**
- Ask ONE question at a time
- Wait for candidate's response before next question
- Accept yes/no or brief answers
- If candidate answers NO to any primary question, proceed to end interview as unsuccessful
- You can ask brief follow-up questions for clarity

"""

    instructions += """### Additional Questions (After Primary Questions)
After primary questions, briefly ask about:
- Availability for the role
- Understanding of job requirements
- Ability to commute to location
- Salary expectations
- Any questions they have about the role

## Critical Rules
- MAXIMUM 300 characters per message (strict limit)
- Ask ONE question at a time
- Keep it conversational and friendly (WhatsApp is more informal than SMS)
- Use emojis sparingly and professionally (✅ ❌ 👍 are acceptable)
- No greetings like "how can I help" - you're conducting an interview
- Say "20 pounds per hour" not "£20ph"
- Use 12-hour format: "8 am" not "08:00"
- Be clear and concise but friendly

## Handling Responses
- Acknowledge responses briefly before moving to next question
- If candidate seems confused, clarify politely
- If candidate asks questions, answer briefly then return to interview
- Keep momentum moving forward

## Ending the Interview
When you determine the interview should end, include EXACTLY one of these tags:

[END_INTERVIEW:unsuccessful] - If candidate:
  * Answers NO to primary questions
  * Is not qualified
  * Declines to continue
  * Gives responses showing they don't meet requirements
  * Message: "Thanks for your time. Unfortunately, you don't meet the requirements for this role. Feel free to apply for other positions with us. All the best! 👍"

[END_INTERVIEW:successful] - If candidate:
  * Answers all questions satisfactorily
  * Meets all requirements
  * Shows genuine interest
  * Message: "Excellent! ✅ You'll receive further instructions soon to submit your ID and certificates. Thanks for your time!"

IMPORTANT: 
- Always include the [END_INTERVIEW:status] tag when ending
- The tag signals the system to mark conversation as complete
- Keep final message under 300 characters including the tag
- Be warm and professional in closing messages
"""

    return instructions


def send_whatsapp_template_message(
    to_number: str,
    from_number: str,
    content_sid: str,
    content_variables: dict,
    organization_id: int,
) -> bool:
    """Send WhatsApp template message via Twilio"""
    try:
        import json

        from twilio.rest import Client

        conf = AIMessageConfig.objects.get(organization_id=organization_id)
        account_sid = conf.twilio_sid
        auth_token = conf.twilio_auth_token

        twilio_client = Client(account_sid, auth_token)

        # Format numbers for WhatsApp
        whatsapp_from = f"whatsapp:{from_number}"
        whatsapp_to = f"whatsapp:{to_number}"

        # CRITICAL: content_variables MUST be a JSON string, not a dict
        content_vars_json = json.dumps(content_variables)

        print(f"Sending template with ContentSid: {content_sid}")
        print(f"ContentVariables: {content_vars_json}")

        # Send template message
        message_obj = twilio_client.messages.create(
            from_=whatsapp_from,
            to=whatsapp_to,
            content_sid=content_sid,
            content_variables=content_vars_json,  # Must be JSON string
        )

        print(f"WhatsApp template message sent successfully: {message_obj.sid}")
        return True

    except Exception as e:
        print(f"Error sending WhatsApp template message: {str(e)}")
        return False


def send_whatsapp_message(
    to_number: str, from_number: str, message: str, organization_id: int
) -> bool:
    """Send WhatsApp message via Twilio WhatsApp API (for follow-up messages within 24hr window)"""
    try:
        from twilio.rest import Client

        twillio_sub_account = TwilioSubAccount.objects.get(
            organization_id=organization_id
        )
        account_sid = twillio_sub_account.twilio_account_sid
        auth_token = twillio_sub_account.twilio_auth_token

        twilio_client = Client(account_sid, auth_token)

        # Format numbers for WhatsApp (must include whatsapp: prefix)
        whatsapp_from = f"whatsapp:{from_number}"
        whatsapp_to = f"whatsapp:{to_number}"

        message_obj = twilio_client.messages.create(
            body=message, from_=whatsapp_from, to=whatsapp_to
        )

        print(f"WhatsApp message sent successfully: {message_obj.sid}")
        return True

    except Exception as e:
        print(f"Error sending WhatsApp message: {str(e)}")
        return False


def get_ai_whatsapp_response(
    conversation_history: List[Dict], ai_instructions: str, candidate_message: str
) -> tuple[str, str]:
    """
    Get AI response for WhatsApp using GPT-4o model.
    Returns: (ai_message, interview_status)
    interview_status: None, 'successful', 'unsuccessful'
    """
    try:
        # Build messages for OpenAI
        messages = [{"role": "system", "content": ai_instructions}]

        # Add conversation history
        for msg in conversation_history:
            role = "assistant" if msg.get("sender") == "ai" else "user"
            messages.append({"role": role, "content": msg.get("message", "")})

        # Add current candidate message
        messages.append({"role": "user", "content": candidate_message})

        # Call OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            max_tokens=200,
            temperature=0.7,
        )

        ai_message = response.choices[0].message.content.strip()

        # Check for interview end tags
        interview_status = None
        if "[END_INTERVIEW:successful]" in ai_message:
            interview_status = "successful"
            ai_message = ai_message.replace("[END_INTERVIEW:successful]", "").strip()
        elif "[END_INTERVIEW:unsuccessful]" in ai_message:
            interview_status = "unsuccessful"
            ai_message = ai_message.replace("[END_INTERVIEW:unsuccessful]", "").strip()

        return ai_message, interview_status

    except Exception as e:
        print(f"Error getting AI WhatsApp response: {str(e)}")
        return (
            "I apologize, but I'm having technical difficulties. Please try again in a moment.",
            None,
        )


@shared_task
def initiate_whatsapp_interview(
    to_number: str,
    from_phone_number: str,
    organization_id: int,
    application_id: int,
    candidate_id: int,
    candidate_name: str,
    job_title: str,
    job_ad_id: int,
    job_details: dict = None,
    primary_questions: list = None,
):
    """Initiate a new WhatsApp interview conversation using template message"""
    try:
        # Get the template SID from environment or database
        # You should store this in your AIMessageConfig model
        conf = AIMessageConfig.objects.get(organization_id=organization_id)
        template_sid = conf.whatsapp_template_sid
        if not template_sid:
            print("Error: TWILIO_WHATSAPP_TEMPLATE_SID not configured")
            return

        # Generate AI instructions
        ai_instructions = generate_ai_whatsapp_instructions(
            job_title=job_title,
            job_id=job_ad_id,
            application_id=application_id,
            candidate_name=candidate_name,
            job_details=job_details or {},
            primary_questions=primary_questions or [],
        )

        # Create the template message content for storage
        # This is what the candidate will see
        template_message = f"Hi {candidate_name}! 👋\n\nThis is Recruitment Direct AI. Thanks for applying for the {job_title} position.\n\nI'd like to ask you a few quick questions about your application. Ready to start? Just reply YES when you're ready!"

        # Prepare template variables for Twilio
        content_variables = {
            "1": candidate_name,  # {{1}} in template
            "2": job_title,  # {{2}} in template
        }

        # Create conversation record
        conversation = InterviewMessageConversation.objects.create(
            organization_id=organization_id,
            application_id=application_id,
            candidate_id=candidate_id,
            candidate_phone=to_number,
            jobad_id=job_ad_id,
            ai_instruction=ai_instructions,
            conversation_json=[
                {
                    "sender": "ai",
                    "message": template_message,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "is_template": True,
                }
            ],
            message_count=1,
            type="AI_WHATSAPP",
            status=ProgressStatus.INITIATED,
        )

        # Send WhatsApp template message
        whatsapp_sent = send_whatsapp_template_message(
            to_number=to_number,
            from_number=from_phone_number,
            content_sid=template_sid,
            content_variables=content_variables,
            organization_id=organization_id,
        )

        if whatsapp_sent:
            print(f"WhatsApp interview initiated for candidate {candidate_id}")
            update_application_status_after_whatsapp(
                organization_id, application_id, "sent"
            )
        else:
            print(f"Failed to send initial WhatsApp template message to {to_number}")

    except Exception as e:
        print(f"Error initiating WhatsApp interview: {str(e)}")


@shared_task
def process_candidate_whatsapp_response(candidate_phone: str, candidate_message: str):
    """Process incoming WhatsApp message from candidate and generate AI response"""
    try:
        # Get conversation
        conversation = (
            InterviewMessageConversation.objects.filter(
                candidate_phone=candidate_phone, type="AI_WHATSAPP"
            )
            .order_by("-created_at")
            .first()
        )

        if not conversation:
            print(f"No WhatsApp conversation found for candidate {candidate_phone}")
            return

        # Update status to IN_PROGRESS on first candidate response
        if conversation.status == ProgressStatus.INITIATED:
            conversation.status = ProgressStatus.IN_PROGRESS

        # Get conversation history
        conversation_history = conversation.conversation_json

        # Add candidate message to history
        candidate_msg = {
            "sender": "candidate",
            "message": candidate_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        conversation_history.append(candidate_msg)

        # Get AI response
        ai_message, interview_status = get_ai_whatsapp_response(
            conversation_history=conversation_history,
            ai_instructions=conversation.ai_instruction,
            candidate_message=candidate_message,
        )

        # Add AI response to history
        ai_msg = {
            "sender": "ai",
            "message": ai_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        conversation_history.append(ai_msg)

        # Update conversation
        conversation.conversation_json = conversation_history
        conversation.message_count += 2

        # Check if interview is complete
        if interview_status:
            conversation.status = ProgressStatus.COMPLETED
            conversation.ai_dicision = interview_status

            # Update application status based on decision
            update_application_status_after_whatsapp(
                conversation.organization_id,
                conversation.application_id,
                interview_status,
            )

        conversation.save()

        # Send AI response via WhatsApp (regular message within 24hr window)
        config = AIMessageConfig.objects.get(
            organization_id=conversation.organization_id, type="AI_WHATSAPP"
        )
        send_whatsapp_message(
            candidate_phone,
            str(config.phone.phone_number),
            ai_message,
            config.organization_id,
        )

        print(
            f"Processed WhatsApp response for candidate {candidate_phone}, status: {interview_status or 'ongoing'}"
        )

    except InterviewMessageConversation.DoesNotExist:
        print(f"No WhatsApp conversation found for candidate {candidate_phone}")
    except Exception as e:
        print(f"Error processing candidate WhatsApp message: {str(e)}")


def update_application_status_after_whatsapp(
    organization_id: int, application_id: int, interview_result: str
):
    """Update application status based on WhatsApp interview result"""
    try:
        config = AIMessageConfig.objects.get(
            organization_id=organization_id, type="AI_WHATSAPP"
        )

        # Determine which status to use
        if interview_result == "sent":
            status_id = config.status_when_sms_is_send
        elif interview_result == "successful":
            status_id = config.status_for_successful_sms
        elif interview_result == "unsuccessful":
            status_id = config.status_for_unsuccessful_sms
        else:
            print(f"Unknown interview result: {interview_result}")
            return

        if not status_id:
            print(f"No status configured for result: {interview_result}")
            return

        # Update via platform API
        platform_api_url = f"{config.platform.base_url}applications/{application_id}"
        access_token = config.platform.access_token

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        payload = {"statusId": status_id}

        response = requests.put(
            platform_api_url, json=payload, headers=headers, timeout=10
        )

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.put(
                    platform_api_url, json=payload, headers=headers, timeout=10
                )

        response.raise_for_status()
        print(
            f"Updated application {application_id} to status {status_id} ({interview_result})"
        )

    except AIMessageConfig.DoesNotExist:
        print(f"No WhatsApp config found for organization {organization_id}")
    except Exception as e:
        print(f"Error updating application status: {str(e)}")


def has_enough_time_passed(updated_at_str: str, waiting_duration_minutes: int) -> bool:
    """Check if enough time has passed since status update"""
    try:
        updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
        current_time = datetime.now(timezone.utc)
        time_diff = (current_time - updated_at).total_seconds() / 60
        return time_diff >= waiting_duration_minutes
    except Exception as e:
        print(f"Error parsing timestamp '{updated_at_str}': {str(e)}")
        return False


def fetch_job_details(job_self_url: str, config):
    """Fetch job details from platform API"""
    access_token = config.platform.access_token
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(job_self_url, headers=headers, timeout=30)
        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.get(job_self_url, headers=headers, timeout=30)

        response.raise_for_status()
        job_data = response.json()

        return {
            "description": job_data.get("description", ""),
            "summary": job_data.get("summary", ""),
            "location": job_data.get("location", {}).get("city", ""),
            "salary": job_data.get("salary", {}).get("description", ""),
            "bulletPoints": job_data.get("bulletPoints", []),
        }
    except Exception as e:
        print(f"Error fetching job details: {str(e)}")
        return {}


@shared_task
def fetch_whatsapp_candidates(config):
    """Fetch candidates eligible for WhatsApp interview"""
    access_token = config.platform.access_token

    # Get primary questions
    primary_questions = []
    question_connections = QuestionMessageConfigConnection.objects.filter(
        config=config
    ).select_related("question")

    for connection in question_connections:
        primary_questions.append(connection.question.question)

    waiting_duration = config.sms_time_after_status_update

    if not access_token:
        print("Error: Could not get access token")
        return []

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    candidates = []

    try:
        # Fetch jobs
        jobs_response = requests.get(
            f"{config.platform.base_url}/jobads",
            headers=headers,
            timeout=30,
        )

        if jobs_response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                jobs_response = requests.get(
                    f"{config.platform.base_url}/jobads",
                    headers=headers,
                    timeout=30,
                )

        jobs_response.raise_for_status()
        jobs_data = jobs_response.json()

        print(f"Found {len(jobs_data.get('items', []))} live jobs for WhatsApp")

        for job in jobs_data.get("items", []):
            time.sleep(0.5)
            temp = False

            if job.get("state") == config.jobad_status_for_sms:
                ad_id = job.get("adId")
                job_title = job.get("title")
                job_self_url = job.get("links", {}).get("self")
                applications_url = job.get("links", {}).get("applications")
                if not applications_url:
                    continue

                job_details = fetch_job_details(job_self_url, config)

                try:
                    # Fetch applications
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
                        candidate_phone = candidate.get("mobile", "")
                        updated_at = application.get("updatedAt", "")
                        status = application.get("status")

                        if candidate_phone and not candidate_phone.startswith("+"):
                            candidate_phone = f"+{candidate_phone}"
                        candidate_phone = candidate_phone.replace(" ", "").replace(
                            "-", ""
                        )

                        # Check if conversation already exists
                        existing_conversation = (
                            InterviewMessageConversation.objects.filter(
                                candidate_id=candidate_id,
                                application_id=application_id,
                                type="AI_WHATSAPP",
                            ).exists()
                        )

                        if existing_conversation:
                            continue

                        if (
                            status.get("statusId") == config.application_status_for_sms
                            and has_enough_time_passed(updated_at, waiting_duration)
                        ):
                            candidate_data = {
                                "to_number": os.getenv("TEST_PHONE_NUMBER"),
                                "from_phone_number": str(config.phone.phone_number),
                                "organization_id": config.organization_id,
                                "application_id": application_id,
                                "candidate_id": candidate_id,
                                "candidate_name": candidate_first_name,
                                "job_title": job_title,
                                "job_ad_id": ad_id,
                                "job_details": job_details,
                                "primary_questions": primary_questions,
                            }

                            candidates.append(candidate_data)
                            print(
                                f"Added WhatsApp candidate: {candidate_first_name} for {job_title}"
                            )
                            temp = True
                            break
                    if temp:
                        break

                except Exception as e:
                    print(f"Error fetching applications for {job_title}: {str(e)}")
                    continue

        print(f"Total WhatsApp candidates: {len(candidates)}")
        return candidates

    except Exception as e:
        print(f"Error fetching WhatsApp candidates: {str(e)}")
        return []


@shared_task
def bulk_whatsapp_interviews(organization_id: int = None):
    """Initiate bulk WhatsApp interviews for an organization"""
    try:
        config = AIMessageConfig.objects.get(
            organization_id=organization_id, type="AI_WHATSAPP"
        )
    except AIMessageConfig.DoesNotExist:
        print(f"No WhatsApp config found for organization {organization_id}")
        return

    candidates = fetch_whatsapp_candidates(config)

    if not candidates:
        print("No candidates to interview via WhatsApp")
        return

    for i, candidate in enumerate(candidates):
        countdown = i * 30

        initiate_whatsapp_interview.apply_async(
            kwargs=candidate,
            countdown=countdown,
        )

    print(f"Scheduled {len(candidates)} WhatsApp interviews")


@shared_task
def initiate_all_whatsapp_interviews():
    """Initiate WhatsApp interviews for all subscribed organizations"""
    organization_ids = Organization.objects.filter().values_list("id", flat=True)
    subscribed_organization_ids = Subscription.objects.filter(
        organization_id__in=organization_ids, available_limit__gt=0
    ).values_list("organization_id", flat=True)

    for organization_id in subscribed_organization_ids:
        print(f"Initiating WhatsApp interviews for organization {organization_id}")
        bulk_whatsapp_interviews.delay(organization_id)
