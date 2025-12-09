import base64
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests
from celery import shared_task
from dotenv import load_dotenv
from openai import OpenAI

from ai_gdpr.choices import ProgressStatus
from ai_gdpr.models import GDPREmailTracker
from common.tasks import send_email_task
from organizations.models import Organization
from subscription.models import Subscription

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)


def encode_organization_id(org_id: int) -> str:
    """Encode organization ID into a URL-safe string"""
    # Create a simple encoded format: ORG-{base64_encoded_id}
    encoded = base64.urlsafe_b64encode(str(org_id).encode()).decode()
    return f"ORG-{encoded}"


def decode_organization_id(encoded_str: str) -> Optional[int]:
    """Decode organization ID from email subject"""
    try:
        # Extract the encoded part after "ORG-"
        if encoded_str.startswith("ORG-"):
            encoded = encoded_str[4:]
            decoded = base64.urlsafe_b64decode(encoded).decode()
            return int(decoded)
        return None
    except Exception as e:
        print(f"Error decoding organization ID: {str(e)}")
        return None


def extract_org_id_from_subject(subject: str) -> Optional[int]:
    """Extract organization ID from email subject line"""
    try:
        # Look for pattern like [ORG-xxxxx] in subject
        import re

        pattern = r"\[ORG-[A-Za-z0-9_-]+\]"
        match = re.search(pattern, subject)
        if match:
            encoded_str = match.group(0)[1:-1]  # Remove brackets
            return decode_organization_id(encoded_str)
        return None
    except Exception as e:
        print(f"Error extracting org ID from subject: {str(e)}")
        return None


def generate_gdpr_email_instructions(
    candidate_name: str,
    candidate_id: int,
    organization_name: str,
) -> str:
    """Generate AI instructions for GDPR consent email conversation"""
    instructions = f"""You are an AI assistant for {organization_name} handling GDPR data retention requests via email.

## Your Task
You are communicating with {candidate_name} (ID: {candidate_id}) regarding their personal data stored in our recruitment system.

## Context
Under GDPR regulations, we need explicit consent to retain candidate data beyond the active recruitment period. This email asks whether the candidate wants us to KEEP or DELETE their data.

## Email Response Guidelines

### Initial Email Question
We ask: "Do you want us to keep your data for future job opportunities? Please reply YES to keep your data, or NO to delete it."

### Handling Candidate Responses

**If candidate agrees to keep data (YES responses):**
- Responses like: "YES", "Yes", "Y", "Keep", "I agree", "OK", "Sure", "Please keep it"
- Your response: "Thank you for your consent! We'll keep your data on file and may contact you about suitable opportunities. You can request deletion anytime."
- Decision: [CONSENT:granted]

**If candidate wants deletion (NO responses):**
- Responses like: "NO", "No", "N", "Delete", "Remove", "I don't agree", "Remove me"
- Your response: "Understood. We'll delete your data within 30 days as per GDPR. You're welcome to reapply in the future."
- Decision: [CONSENT:denied]

**If response is unclear:**
- Ask for clarification: "To confirm, would you like us to KEEP your data (reply YES) or DELETE it (reply NO)? Please reply with YES or NO."
- Do NOT make a decision - wait for clear response

## Critical Rules
- Be professional and respectful
- Keep responses very brief (2-3 sentences max)
- Only mark decision when candidate clearly indicates YES or NO
- Use EXACTLY these tags: [CONSENT:granted] or [CONSENT:denied]
- Never assume - if unclear, ask for YES or NO

## Decision Tags
When candidate makes a clear decision, include EXACTLY one of these tags:
- [CONSENT:granted] - Candidate replied YES
- [CONSENT:denied] - Candidate replied NO

IMPORTANT: Only include the tag when you're certain of the candidate's YES or NO response.
"""
    return instructions


def get_gdpr_ai_response(
    conversation_history: List[Dict],
    ai_instructions: str,
    candidate_message: str,
) -> tuple[str, str]:
    try:
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

        # Check for consent decision tags
        consent_decision = None
        if "[CONSENT:granted]" in ai_message:
            consent_decision = "granted"
            ai_message = ai_message.replace("[CONSENT:granted]", "").strip()
        elif "[CONSENT:denied]" in ai_message:
            consent_decision = "denied"
            ai_message = ai_message.replace("[CONSENT:denied]", "").strip()

        return ai_message, consent_decision

    except Exception as e:
        print(f"Error getting AI response for GDPR: {str(e)}")
        return (
            "We apologize for the technical difficulty. Please reply with YES or NO to indicate your preference.",
            None,
        )


def get_interval_timedelta(interval_choice: str) -> timedelta:
    """Convert interval choice to timedelta"""
    interval_map = {
        "6_MONTH": timedelta(days=180),
        "12_MONTH": timedelta(days=360),
        "24_MONTH": timedelta(days=720),
        "36_MONTH": timedelta(days=1080),
        "48_MONTH": timedelta(days=1440),
    }
    return interval_map.get(interval_choice, timedelta(days=365))


def fetch_last_action_date(
    config, candidate_id: int, base_url: str, headers: dict
) -> Optional[datetime]:
    """Fetch the most recent action date based on config settings"""
    last_dates = []

    try:
        # Get last application date
        if config.should_use_last_application_date:
            try:
                response = requests.get(
                    f"{base_url}candidates/{candidate_id}/applications",
                    headers=headers,
                    timeout=30,
                )
                if response.status_code == 200:
                    applications = response.json().get("items", [])
                    if applications:
                        app_dates = [
                            datetime.fromisoformat(
                                app.get("createdAt").replace("Z", "+00:00")
                            )
                            for app in applications
                            if app.get("createdAt")
                        ]
                        if app_dates:
                            last_dates.append(max(app_dates))
            except Exception as e:
                print(
                    f"Error fetching applications for candidate {candidate_id}: {str(e)}"
                )

        # Get last placement date
        if config.should_use_last_placement_date:
            try:
                response = requests.get(
                    f"{base_url}candidates/{candidate_id}/placements",
                    headers=headers,
                    timeout=30,
                )
                if response.status_code == 200:
                    placements = response.json().get("items", [])
                    if placements:
                        placement_dates = [
                            datetime.fromisoformat(
                                pl.get("createdAt").replace("Z", "+00:00")
                            )
                            for pl in placements
                            if pl.get("createdAt")
                        ]
                        if placement_dates:
                            last_dates.append(max(placement_dates))
            except Exception as e:
                print(
                    f"Error fetching placements for candidate {candidate_id}: {str(e)}"
                )

        # Get last activity creation date
        if config.should_use_activity_creation_date:
            try:
                response = requests.get(
                    f"{base_url}candidates/{candidate_id}/activities",
                    headers=headers,
                    timeout=30,
                )
                if response.status_code == 200:
                    activities = response.json().get("items", [])
                    if activities:
                        activity_dates = [
                            datetime.fromisoformat(
                                act.get("createdAt").replace("Z", "+00:00")
                            )
                            for act in activities
                            if act.get("createdAt")
                        ]
                        if activity_dates:
                            last_dates.append(max(activity_dates))
            except Exception as e:
                print(
                    f"Error fetching activities for candidate {candidate_id}: {str(e)}"
                )

        # Get last note creation date
        if config.should_use_last_note_creatation_date:
            try:
                response = requests.get(
                    f"{base_url}candidates/{candidate_id}/notes",
                    headers=headers,
                    timeout=30,
                )
                if response.status_code == 200:
                    notes = response.json().get("items", [])
                    if notes:
                        note_dates = [
                            datetime.fromisoformat(
                                note.get("createdAt").replace("Z", "+00:00")
                            )
                            for note in notes
                            if note.get("createdAt")
                        ]
                        if note_dates:
                            last_dates.append(max(note_dates))
            except Exception as e:
                print(f"Error fetching notes for candidate {candidate_id}: {str(e)}")

        # Return the most recent date from all selected options
        if last_dates:
            return max(last_dates)

        return None

    except Exception as e:
        print(f"Error in fetch_last_action_date: {str(e)}")
        return None


def should_send_gdpr_email(
    config,
    candidate_id: int,
    candidate_email: str,
    last_action_date: Optional[datetime],
    candidate_updated_at: Optional[datetime],
) -> bool:
    """Determine if GDPR email should be sent based on intervals and tracker status"""
    return True

    if not last_action_date and not candidate_updated_at:
        return False

    # Use candidate update date if selected and no other action dates available
    if (
        config.should_use_candidate_update_date
        and not last_action_date
        and candidate_updated_at
    ):
        last_action_date = candidate_updated_at
    elif (
        last_action_date
        and candidate_updated_at
        and config.should_use_candidate_update_date
    ):
        # If both exist, use the most recent
        last_action_date = max(last_action_date, candidate_updated_at)

    if not last_action_date:
        return False

    # Get interval timedelta
    interval_delta = get_interval_timedelta(config.interval_from_last_action)
    current_time = datetime.now(timezone.utc)

    # Check if interval has passed since last action
    time_since_action = current_time - last_action_date
    if time_since_action < interval_delta:
        return False

    # Check if there's an existing tracker
    existing_tracker = (
        GDPREmailTracker.objects.filter(
            email=candidate_email,
            organization_id=config.organization_id,
        )
        .order_by("-updated_at")
        .first()
    )

    if not existing_tracker:
        # No tracker exists, send email
        return True

    # Check if interval has passed since last tracker update
    time_since_tracker_update = current_time - existing_tracker.updated_at

    if time_since_tracker_update >= interval_delta:
        # Reset the tracker
        reset_gdpr_tracker(existing_tracker)
        return True

    return False


def reset_gdpr_tracker(tracker: GDPREmailTracker):
    """Reset GDPR tracker fields for a new consent cycle"""
    tracker.conversation_json = []
    tracker.message_count = 0
    tracker.status = ProgressStatus.INITIATED
    tracker.is_candidate_agree = False
    tracker.ai_dicision = None
    tracker.save()
    print(f"Reset GDPR tracker for email {tracker.email}")


def fetch_candidates_from_platform(config) -> List[Dict]:
    """Fetch candidates and determine who needs GDPR emails"""
    access_token = config.platform.access_token
    base_url = config.platform.base_url

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    candidates_list = []

    try:
        response = requests.get(
            f"{base_url}candidates",
            headers=headers,
            timeout=30,
        )
        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.get(
                    f"{base_url}/candidates",
                    headers=headers,
                    timeout=30,
                )

        response.raise_for_status()
        data = response.json()

        for candidate in data.get("items", []):
            candidate_id = candidate.get("candidateId")
            email = candidate.get("email")
            first_name = candidate.get("firstName", "")
            last_name = candidate.get("lastName", "")
            updated_at_str = candidate.get("updatedAt")

            if not email:
                continue

            # Parse candidate updated date
            candidate_updated_at = None
            if updated_at_str:
                try:
                    candidate_updated_at = datetime.fromisoformat(
                        updated_at_str.replace("Z", "+00:00")
                    )
                except Exception as e:
                    print(
                        f"Error parsing updatedAt for candidate {candidate_id}: {str(e)}"
                    )

            # Fetch last action date based on config
            last_action_date = fetch_last_action_date(
                config, candidate_id, base_url, headers
            )

            # Determine if email should be sent
            if should_send_gdpr_email(
                config,
                candidate_id,
                email,
                last_action_date,
                candidate_updated_at,
            ):
                candidates_list.append(
                    {
                        "candidate_id": candidate_id,
                        "email": "osmangoni255@gmail.com",
                        "first_name": first_name,
                        "last_name": last_name,
                        "full_name": f"{first_name} {last_name}".strip(),
                        "last_action_date": last_action_date.isoformat()
                        if last_action_date
                        else None,
                    }
                )
            break

        print(f"Found {len(candidates_list)} candidates eligible for GDPR emails")
        return candidates_list

    except Exception as e:
        print(f"Error fetching candidates: {str(e)}")
        return []


@shared_task
def initiate_gdpr_consent_email(
    email: str,
    candidate_id: int,
    candidate_name: str,
    organization_id: int,
    platform_id: int,
    organization_name: str,
):
    try:
        from ai_gdpr.models import GDPREmailConfig

        config = GDPREmailConfig.objects.get(organization_id=organization_id)
        organization = Organization.objects.get(id=organization_id)
        organization_name = organization.name

    except (GDPREmailConfig.DoesNotExist, Organization.DoesNotExist):
        print(f"Config or organization not found for organization {organization_id}")
        return

    try:
        ai_instructions = generate_gdpr_email_instructions(
            candidate_name=candidate_name,
            candidate_id=candidate_id,
            organization_name=organization_name,
        )

        # Encode organization ID and add to subject
        org_encoded = encode_organization_id(organization_id)
        subject = (
            f"Important: Your Data Privacy Rights - Action Required [{org_encoded}]"
        )

        email_context = {
            "candidate_name": candidate_name,
            "organization_name": organization_name,
        }

        # Store the email content for conversation history
        initial_email_content = f"""Dear {candidate_name},

We hope this message finds you well. As part of our commitment to data privacy and GDPR compliance, we're reaching out regarding your personal information stored in our recruitment system.

**Your Rights:**
Under GDPR, you have control over your personal data. We currently hold your contact details, CV, and application history.

**Your Choice:**
We need your consent to keep your data for future job opportunities. If we don't hear from you within 30 days, we'll be required to delete your data as per GDPR regulations.

**Please reply to this email with:**
- **YES** - to allow us to keep your data and contact you about future opportunities
- **NO** - to have your information permanently deleted within 30 days

Best regards,
{organization_name} Recruitment Team"""

        # Create or update tracker record
        tracker, created = GDPREmailTracker.objects.update_or_create(
            email=email,
            organization_id=organization_id,
            defaults={
                "candidate_id": candidate_id,
                "config_id": config.id,
                "ai_instruction": ai_instructions,
                "conversation_json": [
                    {
                        "sender": "ai",
                        "message": initial_email_content,
                        "subject": subject,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                ],
                "message_count": 1,
                "status": ProgressStatus.INITIATED,
                "is_candidate_agree": False,
                "ai_dicision": None,
            },
        )

        send_email_task.delay(
            subject=subject,
            recipient=email,
            template_name="emails/gdpr_consent_email.html",
            context=email_context,
        )

        print(f"GDPR consent email sent to {email} (Candidate ID: {candidate_id})")

    except Exception as e:
        print(f"Error initiating GDPR consent email: {str(e)}")


@shared_task
def process_candidate_email_response(
    email: str,
    candidate_message: str,
    organization_id: int,
    subject: str = None,
):
    """
    Process candidate email response

    Args:
        email: Candidate email address
        candidate_message: Message content from candidate
        organization_id: Organization ID (extracted from webhook or passed directly)
        subject: Email subject line (optional, used to extract org_id if not provided)
    """
    try:
        # If organization_id is not provided, try to extract from subject
        if not organization_id and subject:
            organization_id = extract_org_id_from_subject(subject)
            if not organization_id:
                print(f"Could not extract organization ID from subject: {subject}")
                return

        tracker = (
            GDPREmailTracker.objects.filter(
                email=email,
                organization_id=organization_id,
            )
            .order_by("-created_at")
            .first()
        )

        if not tracker:
            print(f"No GDPR tracker found for email {email}")
            return

        if tracker.status == ProgressStatus.INITIATED:
            tracker.status = ProgressStatus.IN_PROGRESS

        conversation_history = tracker.conversation_json
        candidate_msg = {
            "sender": "candidate",
            "message": candidate_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        conversation_history.append(candidate_msg)

        ai_message, consent_decision = get_gdpr_ai_response(
            conversation_history=conversation_history,
            ai_instructions=tracker.ai_instruction,
            candidate_message=candidate_message,
        )

        ai_msg = {
            "sender": "ai",
            "message": ai_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        conversation_history.append(ai_msg)

        tracker.conversation_json = conversation_history
        tracker.message_count += 2

        if consent_decision:
            tracker.status = ProgressStatus.COMPLETED
            tracker.ai_dicision = consent_decision
            tracker.is_candidate_agree = consent_decision == "granted"

        tracker.save()

        try:
            organization = Organization.objects.get(id=organization_id)
            organization_name = organization.name
        except Organization.DoesNotExist:
            organization_name = "Recruitment Team"

        # Include organization ID in response subject as well
        org_encoded = encode_organization_id(organization_id)
        response_subject = f"Re: Your Data Privacy Rights [{org_encoded}]"

        send_email_task.delay(
            subject=response_subject,
            recipient=email,
            template_name="gdpr_response_email.html",
            context={
                "message": ai_message,
                "organization_name": organization_name,
            },
        )

        print(
            f"Processed GDPR email response for {email}, decision: {consent_decision or 'pending'}"
        )

    except Exception as e:
        print(f"Error processing candidate email response: {str(e)}")


@shared_task
def bulk_gdpr_consent_emails(organization_id: int = None):
    try:
        from ai_gdpr.models import GDPREmailConfig

        config = GDPREmailConfig.objects.get(organization_id=organization_id)
        organization = Organization.objects.get(id=organization_id)
        organization_name = organization.name

    except (GDPREmailConfig.DoesNotExist, Organization.DoesNotExist):
        print(f"Config or organization not found for organization {organization_id}")
        return

    candidates = fetch_candidates_from_platform(config)

    if not candidates:
        print("No candidates to send GDPR emails")
        return

    for i, candidate in enumerate(candidates):
        countdown = i * 10

        initiate_gdpr_consent_email.apply_async(
            kwargs={
                "email": candidate["email"],
                "candidate_id": candidate["candidate_id"],
                "candidate_name": candidate["full_name"],
                "organization_id": organization_id,
                "platform_id": config.platform_id,
                "organization_name": organization_name,
            },
            countdown=countdown,
        )

    print(f"Scheduled {len(candidates)} GDPR consent emails")


@shared_task
def initiate_all_gdpr_emails():
    """Initiate GDPR emails for all subscribed organizations"""
    organization_ids = Organization.objects.filter().values_list("id", flat=True)
    subscribed_organization_ids = Subscription.objects.filter(
        organization_id__in=organization_ids,
        available_limit__gt=0,
    ).values_list("organization_id", flat=True)

    for organization_id in subscribed_organization_ids:
        print(f"Initiating GDPR emails for organization {organization_id}")
        bulk_gdpr_consent_emails.delay(organization_id)
