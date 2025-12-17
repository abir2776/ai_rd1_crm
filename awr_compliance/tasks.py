import base64
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests
from celery import shared_task
from dotenv import load_dotenv

from awr_compliance.models import AWRConfig, AWRTracker
from common.tasks import send_email_task
from organizations.models import Organization
from subscription.models import Subscription

load_dotenv()


def encode_organization_id(org_id: int) -> str:
    """Encode organization ID into a URL-safe string"""
    encoded = base64.urlsafe_b64encode(str(org_id).encode()).decode()
    return f"ORG-{encoded}"


def decode_organization_id(encoded_str: str) -> Optional[int]:
    """Decode organization ID from email subject"""
    try:
        if encoded_str.startswith("ORG-"):
            encoded = encoded_str[4:]
            decoded = base64.urlsafe_b64decode(encoded).decode()
            return int(decoded)
        return None
    except Exception as e:
        print(f"Error decoding organization ID: {str(e)}")
        return None


def should_send_awr_email(
    config: AWRConfig,
    placement_id: int,
) -> bool:
    """Check if we've already sent an email for this placement"""

    # Check if there's an existing tracker for this placement
    existing_tracker = AWRTracker.objects.filter(
        config=config,
        placement_id=placement_id,
    ).first()

    if not existing_tracker:
        # No tracker exists, should send email
        return True

    # Check if enough time has passed since last email (e.g., 7 days cooldown)
    current_time = datetime.now(timezone.utc)
    time_since_last_email = current_time - existing_tracker.last_sent_at

    # Don't resend within 7 days
    if time_since_last_email < timedelta(days=7):
        return False

    return True


def fetch_placements_from_platform(config: AWRConfig) -> List[Dict]:
    """Fetch placements based on AWR configuration criteria"""
    access_token = config.platform.access_token
    base_url = config.platform.base_url

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    eligible_placements = []

    try:
        # Calculate date threshold for StartDate filter
        placement_started_before = config.placement_started_before_days
        expiry_threshold = (
            (datetime.now(timezone.utc) - timedelta(days=placement_started_before))
            .date()
            .isoformat()
        )
        another_expiry_threshold = (
            (datetime.fromisoformat(expiry_threshold) - timedelta(days=1))
            .date()
            .isoformat()
        )

        # Build query parameters according to specification
        params = {
            "StartDate": [f"<{expiry_threshold}", f">{another_expiry_threshold}"],
            "Approved": True,
            "StatusId": config.selected_status_ids,
            "Limit": 1000,
        }

        response = requests.get(
            f"{base_url}placements",
            headers=headers,
            params=params,
            timeout=30,
        )

        # Handle token refresh if needed
        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.get(
                    f"{base_url}placements",
                    headers=headers,
                    params=params,
                    timeout=30,
                )

        response.raise_for_status()
        data = response.json()

        # Process each placement and fetch detailed information
        for placement in data.get("items", []):
            placement_id = placement.get("placementId")

            if not placement_id:
                continue

            # Fetch detailed placement information
            try:
                detail_response = requests.get(
                    f"{base_url}placements/{placement_id}",
                    headers=headers,
                    timeout=30,
                )

                if detail_response.status_code == 401:
                    access_token = config.platform.refresh_access_token()
                    if access_token:
                        headers["Authorization"] = f"Bearer {access_token}"
                        detail_response = requests.get(
                            f"{base_url}v2/placements/{placement_id}",
                            headers=headers,
                            timeout=30,
                        )

                detail_response.raise_for_status()
                placement_detail = detail_response.json()

            except Exception as e:
                print(f"Error fetching placement {placement_id} details: {str(e)}")
                continue

            # Extract payment type from detailed data
            payment_type = placement_detail.get("paymentType")

            # Check if payment type matches selected payment types
            if payment_type not in config.selected_payment_types:
                print(
                    f"Placement {placement_id} payment type '{payment_type}' not in selected types"
                )
                continue

            # Extract contact information
            contact = placement_detail.get("contact", {})
            contact_email = contact.get("email")
            contact_first_name = contact.get("firstName", "")
            contact_last_name = contact.get("lastName", "")

            if not contact_email:
                print(f"No contact email for placement {placement_id}")
                continue

            # Extract candidate information
            candidate = placement_detail.get("candidate", {})
            candidate_first_name = candidate.get("firstName", "")
            candidate_last_name = candidate.get("lastName", "")

            # Extract job information
            job_title = placement_detail.get("jobTitle", "")
            start_date = placement_detail.get("startDate", "")

            # Check if we should send email for this placement
            if should_send_awr_email(config, placement_id):
                eligible_placements.append(
                    {
                        "placement_id": placement_id,
                        "contact_email": "osmangoni255@gmail.com",
                        "contact_first_name": contact_first_name,
                        "contact_last_name": contact_last_name,
                        "candidate_first_name": candidate_first_name,
                        "candidate_last_name": candidate_last_name,
                        "job_title": job_title,
                        "start_date": start_date,
                        "payment_type": payment_type,
                    }
                )
                break

                print(f"Added placement {placement_id} to eligible list")

        print(f"Found {len(eligible_placements)} eligible placements for AWR emails")
        return eligible_placements

    except Exception as e:
        print(f"Error fetching placements: {str(e)}")
        return []


@shared_task
def initiate_awr_compliance_email(
    placement_id: int,
    contact_email: str,
    contact_first_name: str,
    contact_last_name: str,
    candidate_first_name: str,
    candidate_last_name: str,
    job_title: str,
    organization_id: int,
    config_id: int,
):
    """Send AWR compliance email for a specific placement"""
    try:
        config = AWRConfig.objects.get(id=config_id)
        organization = Organization.objects.get(id=organization_id)
        organization_name = organization.name

    except (AWRConfig.DoesNotExist, Organization.DoesNotExist):
        print(f"Config or organization not found for organization {organization_id}")
        return

    try:
        # Encode organization ID and add to subject
        org_encoded = encode_organization_id(organization_id)
        subject = f"AWR Compliance: Action Required for Placement #{placement_id} [{org_encoded}]"

        # Prepare email context with placement details
        contact_full_name = f"{contact_first_name} {contact_last_name}".strip()
        candidate_full_name = f"{candidate_first_name} {candidate_last_name}".strip()

        email_context = {
            "contact_first_name": contact_first_name,
            "contact_last_name": contact_last_name,
            "contact_full_name": contact_full_name,
            "candidate_first_name": candidate_first_name,
            "candidate_last_name": candidate_last_name,
            "candidate_full_name": candidate_full_name,
            "organization_name": organization_name,
            "placement_id": placement_id,
            "job_title": job_title,
            "weeks_threshold": config.placement_started_before_days // 7,
        }

        # Create or update tracker record
        tracker, created = AWRTracker.objects.update_or_create(
            config=config,
            placement_id=placement_id,
            defaults={
                "contact_email": contact_email,
                "last_sent_at": datetime.now(timezone.utc),
            },
        )

        # Send email with configured template, sender, and reply-to
        send_email_task.delay(
            subject=subject,
            recipient=contact_email,
            template_name=config.email_template_name,
            context=email_context,
            customer_email=config.email_sender,
            reply_to=config.email_reply_to,
        )

        action = "created" if created else "updated"
        print(
            f"AWR email sent to {contact_email} for placement {placement_id} (Tracker {action})"
        )

    except Exception as e:
        print(f"Error initiating AWR compliance email: {str(e)}")


@shared_task
def bulk_awr_compliance_emails(organization_id: int):
    """Send AWR compliance emails for all eligible placements in an organization"""
    try:
        config = AWRConfig.objects.get(organization_id=organization_id)
        organization = Organization.objects.get(id=organization_id)

    except (AWRConfig.DoesNotExist, Organization.DoesNotExist):
        print(f"Config or organization not found for organization {organization_id}")
        return

    # Fetch eligible placements based on config criteria
    placements = fetch_placements_from_platform(config)

    if not placements:
        print(f"No eligible placements found for organization {organization_id}")
        return

    # Schedule emails with delay to avoid overwhelming the email system
    for i, placement in enumerate(placements):
        countdown = i * 10  # 10 seconds delay between each email

        initiate_awr_compliance_email.apply_async(
            kwargs={
                "placement_id": placement["placement_id"],
                "contact_email": placement["contact_email"],
                "contact_first_name": placement["contact_first_name"],
                "contact_last_name": placement["contact_last_name"],
                "candidate_first_name": placement["candidate_first_name"],
                "candidate_last_name": placement["candidate_last_name"],
                "job_title": placement["job_title"],
                "organization_id": organization_id,
                "config_id": config.id,
            },
            countdown=countdown,
        )

    print(
        f"Scheduled {len(placements)} AWR compliance emails for organization {organization.name}"
    )


@shared_task
def initiate_all_awr_emails():
    """Initiate AWR compliance emails for all subscribed organizations"""
    organization_ids = Organization.objects.filter().values_list("id", flat=True)

    # Filter organizations with active subscriptions
    subscribed_organization_ids = Subscription.objects.filter(
        organization_id__in=organization_ids,
        available_limit__gt=0,
    ).values_list("organization_id", flat=True)

    for organization_id in subscribed_organization_ids:
        print(f"Initiating AWR compliance emails for organization {organization_id}")
        bulk_awr_compliance_emails.delay(organization_id)

    print(
        f"Initiated AWR email tasks for {len(subscribed_organization_ids)} organizations"
    )
