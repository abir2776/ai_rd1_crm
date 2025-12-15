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


def get_interval_timedelta(interval_choice: str) -> timedelta:
    """Convert interval choice to timedelta"""
    interval_map = {
        "6_MONTH": timedelta(days=180),
        "12_MONTH": timedelta(days=365),
        "24_MONTH": timedelta(days=730),
        "36_MONTH": timedelta(days=1095),
    }
    return interval_map.get(interval_choice, timedelta(days=365))


def fetch_main_contact_email(
    company_main_contact_url: str, headers: dict
) -> Optional[str]:
    """Fetch main contact email from company"""
    try:
        response = requests.get(
            company_main_contact_url,
            headers=headers,
            timeout=30,
        )

        if response.status_code == 200:
            contact_data = response.json()
            email = contact_data.get("email")
            unsubscribed = contact_data.get("unsubscribed", False)

            # Only return email if contact is not unsubscribed
            if email and not unsubscribed:
                return email

        return None

    except Exception as e:
        print(f"Error fetching main contact from {company_main_contact_url}: {str(e)}")
        return None


def should_send_awr_email(
    config: AWRConfig,
    company_email: str,
    placement_created_at: datetime,
) -> bool:
    """Determine if AWR email should be sent based on interval and tracker status"""

    if not placement_created_at:
        return False

    # Get interval timedelta
    interval_delta = get_interval_timedelta(config.interval)
    current_time = datetime.now(timezone.utc)

    # Check if interval has passed since placement creation
    time_since_placement = current_time - placement_created_at
    if time_since_placement < interval_delta:
        return False

    # Check if there's an existing tracker for this email
    existing_tracker = (
        AWRTracker.objects.filter(
            email=company_email,
            config__organization_id=config.organization_id,
        )
        .order_by("-updated_at")
        .first()
    )

    if not existing_tracker:
        # No tracker exists, send email
        return True

    # Check if interval has passed since last tracker update
    time_since_last_email = current_time - existing_tracker.updated_at

    if time_since_last_email >= interval_delta:
        # Interval has passed, send new email
        return True

    return False


def fetch_placements_from_platform(config: AWRConfig) -> List[Dict]:
    """Fetch placements and determine which companies need AWR emails"""
    access_token = config.platform.access_token
    base_url = config.platform.base_url

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    companies_to_email = []

    try:
        response = requests.get(
            f"{base_url}placements",
            headers=headers,
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
                    timeout=30,
                )

        response.raise_for_status()
        data = response.json()

        processed_emails = set()  # Track processed emails to avoid duplicates

        for placement in data.get("items", []):
            placement_id = placement.get("placementId")
            job_title = placement.get("jobTitle", "")
            created_at_str = placement.get("createdAt")

            # Parse placement creation date
            placement_created_at = None
            if created_at_str:
                try:
                    placement_created_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                except Exception as e:
                    print(
                        f"Error parsing createdAt for placement {placement_id}: {str(e)}"
                    )
                    continue

            # Extract company information
            job = placement.get("job", {})
            company = job.get("company", {})
            company_id = company.get("companyId")
            company_name = company.get("name", "")

            if not company_id or not company_name:
                continue

            # Get main contact link
            company_links = company.get("links", {})
            main_contact_url = company_links.get("mainContact")

            if not main_contact_url:
                print(
                    f"No main contact link for company {company_name} (ID: {company_id})"
                )
                continue

            # Fetch main contact email
            company_email = fetch_main_contact_email(main_contact_url, headers)

            if not company_email:
                print(
                    f"No valid email found for company {company_name} (ID: {company_id})"
                )
                continue

            # Skip if we've already processed this email in this batch
            if company_email in processed_emails:
                continue

            # Determine if email should be sent
            if should_send_awr_email(config, company_email, placement_created_at):
                companies_to_email.append(
                    {
                        "company_id": company_id,
                        "company_name": company_name,
                        "company_email": "osmangoni255@gmail.com",
                        "placement_id": placement_id,
                        "job_title": job_title,
                        "placement_created_at": placement_created_at.isoformat(),
                    }
                )
                processed_emails.add(company_email)
                break

        print(f"Found {len(companies_to_email)} companies eligible for AWR emails")
        return companies_to_email

    except Exception as e:
        print(f"Error fetching placements: {str(e)}")
        return []


@shared_task
def initiate_awr_compliance_email(
    email: str,
    company_id: int,
    company_name: str,
    organization_id: int,
    placement_id: int,
    job_title: str,
):
    """Send AWR compliance email to company"""
    try:
        config = AWRConfig.objects.get(organization_id=organization_id)
        organization = Organization.objects.get(id=organization_id)
        organization_name = organization.name

    except (AWRConfig.DoesNotExist, Organization.DoesNotExist):
        print(f"Config or organization not found for organization {organization_id}")
        return

    try:
        # Encode organization ID and add to subject
        org_encoded = encode_organization_id(organization_id)
        subject = f"AWR Compliance: Action Required for Placement #{placement_id} [{org_encoded}]"

        email_context = {
            "company_name": company_name,
            "organization_name": organization_name,
            "placement_id": placement_id,
            "job_title": job_title,
        }

        # Create or update tracker record
        tracker, created = AWRTracker.objects.update_or_create(
            email=email,
            config_id=config.id,
            defaults={
                "updated_at": datetime.now(timezone.utc),
            },
        )

        send_email_task.delay(
            subject=subject,
            recipient=email,
            template_name="emails/awr_compliance_email.html",
            context=email_context,
        )

        action = "created" if created else "updated"
        print(
            f"AWR compliance email sent to {email} (Company: {company_name}, Tracker {action})"
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

    # Fetch placements and eligible companies
    companies = fetch_placements_from_platform(config)

    if not companies:
        print(f"No companies to send AWR emails for organization {organization_id}")
        return

    # Schedule emails with delay to avoid overwhelming the email system
    for i, company in enumerate(companies):
        countdown = i * 10  # 10 seconds delay between each email

        initiate_awr_compliance_email.apply_async(
            kwargs={
                "email": company["company_email"],
                "company_id": company["company_id"],
                "company_name": company["company_name"],
                "organization_id": organization_id,
                "placement_id": company["placement_id"],
                "job_title": company["job_title"],
            },
            countdown=countdown,
        )

    print(
        f"Scheduled {len(companies)} AWR compliance emails for organization {organization.name}"
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
