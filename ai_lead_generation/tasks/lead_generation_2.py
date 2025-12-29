import json
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from celery import shared_task
from dotenv import load_dotenv
from jsonschema import Draft202012Validator
from openai import OpenAI

from ai_lead_generation.models import MarketingAutomationConfig
from subscription.models import Subscription

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API")
MODEL = "gpt-4o"


def return_Schema() -> Dict[str, Any]:
    """
    Returns the JSON schema for validating AI-extracted company hiring information.
    """
    SCHEMA: Dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "Is Hiring actively": {
                "type": "string",
                "enum": ["Yes", "No", "null"],
                "description": "Whether the company is actively hiring",
            },
            "Hiring Job Title/Position": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of job titles/positions the company is hiring for",
            },
            "Is agency": {
                "type": "string",
                "enum": ["Yes", "No", "null"],
                "description": "Whether the company is a recruitment agency",
            },
        },
        "required": ["Is Hiring actively", "Hiring Job Title/Position", "Is agency"],
    }
    return SCHEMA


def get_hiring_detection_instructions() -> Tuple[str, str]:
    """
    Returns system and user instructions for AI-based hiring detection.

    Returns:
        Tuple of (system_instructions, user_instructions_template)
    """
    SYSTEM_INSTRUCTIONS = (
        "You are an AI assistant specialized in analyzing companies to determine if they are actively hiring.\n"
        "Your task is to search the web for information about a company and determine:\n"
        "1. Whether the company is actively hiring (Yes/No)\n"
        "2. What job titles/positions they are hiring for (if any)\n"
        "3. Whether the company is a recruitment agency (Yes/No)\n\n"
        "Guidelines:\n"
        "- Search for recent job postings, career pages, and hiring announcements\n"
        "- Look for evidence of active recruitment (job boards, company career pages, LinkedIn)\n"
        "- Identify specific job titles being recruited\n"
        "- Determine if the company is a recruitment/staffing agency\n"
        "- Return 'null' if information cannot be determined\n"
        "- Return ONLY raw JSON matching the specified structure (no markdown, no extra text)\n\n"
        "Output format:\n"
        "{\n"
        '  "Is Hiring actively": "Yes" | "No" | "null",\n'
        '  "Hiring Job Title/Position": ["Job Title 1", "Job Title 2", ...] or ["null"],\n'
        '  "Is agency": "Yes" | "No" | "null"\n'
        "}\n"
    )

    USER_INSTRUCTIONS_TEMPLATE = (
        "Analyze the following company and determine if they are actively hiring:\n\n"
        "{text}\n\n"
        "Search online for recent hiring information about this company.\n"
        "Return ONLY raw JSON matching the specified structure (no markdown, no extra text)."
    )

    return SYSTEM_INSTRUCTIONS, USER_INSTRUCTIONS_TEMPLATE


def strip_code_fences(s: str) -> str:
    """Remove markdown code fences from a string."""
    s = s.strip()
    if s.startswith("```"):
        s = s.strip("`").strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()
    return s


def find_json_block(s: str) -> str:
    """Extract JSON object from text that may contain other content."""
    import re

    s = s.strip()
    obj_match = re.search(r"\{.*\}\s*$", s, flags=re.DOTALL)
    if obj_match:
        return obj_match.group(0)
    return s


def normalize_nulls(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize null values in the data structure.
    Converts None, empty strings, and whitespace-only strings to the literal string "null".
    """

    def to_str_null(v: Any) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "null"
        return str(v).strip() if isinstance(v, str) else str(v)

    # Normalize top-level fields
    if "Is Hiring actively" in data:
        data["Is Hiring actively"] = to_str_null(data["Is Hiring actively"])

    if "Is agency" in data:
        data["Is agency"] = to_str_null(data["Is agency"])

    # Normalize job titles array
    if "Hiring Job Title/Position" in data:
        job_titles = data["Hiring Job Title/Position"]
        if isinstance(job_titles, list):
            data["Hiring Job Title/Position"] = [
                to_str_null(title) for title in job_titles
            ]
        else:
            data["Hiring Job Title/Position"] = ["null"]

    return data


def detect_company_hiring_status(
    company_name: str, company_address: str
) -> Optional[Dict[str, Any]]:
    """
    Use AI to detect if a company is actively hiring.

    Args:
        company_name: Name of the company
        company_address: Address/location of the company

    Returns:
        Dictionary with hiring status, job titles, and agency status, or None on error
    """
    try:
        SCHEMA = return_Schema()
        SYSTEM_INSTRUCTIONS, USER_INSTRUCTIONS_TEMPLATE = (
            get_hiring_detection_instructions()
        )

        business_info = f"Company name: {company_name}\nAddress: {company_address}"

        client = OpenAI(api_key=OPENAI_API_KEY)

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                {
                    "role": "user",
                    "content": USER_INSTRUCTIONS_TEMPLATE.format(text=business_info),
                },
            ],
        )

        raw = response.choices[0].message.content or ""
        content = strip_code_fences(raw)

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            candidate = find_json_block(content)
            data = json.loads(candidate)

        # Validate against schema
        Draft202012Validator(SCHEMA).validate(data)

        # Normalize null values
        data = normalize_nulls(data)

        print(f"  ✓ AI Analysis completed for: {company_name}")
        return data

    except Exception as e:
        print(f"  ✗ Error analyzing company: {str(e)}")
        return None


def fetch_all_companies(config: MarketingAutomationConfig) -> List[Dict[str, Any]]:
    try:
        access_token = config.platform.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        companies_url = f"{config.platform.base_url}/companies"
        params = {"Limit": 100}

        response = requests.get(
            companies_url, headers=headers, params=params, timeout=30
        )

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.get(
                    companies_url, headers=headers, params=params, timeout=30
                )

        if response.status_code == 200:
            companies = response.json().get("items", [])
            print(f"✓ Fetched {len(companies)} companies")
            return companies

        return []

    except Exception as e:
        print(f"✗ Error fetching companies: {str(e)}")
        return []


def create_opportunity(
    company_id: int,
    job_title: str,
    owner_user_ids: list,
    config: MarketingAutomationConfig,
) -> bool:
    try:
        access_token = config.platform.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        opportunities_url = f"{config.platform.base_url}/opportunities"

        payload = {
            "opportunityTitle": job_title if job_title else "Unknown Job Title",
            "companyId": company_id,
            "ownerUserIds": owner_user_ids,
        }
        if config.opportunity_stage:
            payload["stageId"] = config.opportunity_stage

        response = requests.post(
            opportunities_url, json=payload, headers=headers, timeout=30
        )

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.post(
                    opportunities_url, json=payload, headers=headers, timeout=30
                )

        if response.status_code in [200, 201]:
            opportunity_id = response.json().get("opportunityId")
            print(f"    ✓ Created opportunity: {job_title} (ID: {opportunity_id})")
            return True

        print(f"    ✗ Failed to create opportunity: {response.status_code}")
        return False

    except Exception as e:
        print(f"    ✗ Error creating opportunity: {str(e)}")
        return False


def process_company_for_marketing(
    company: Dict[str, Any], config: MarketingAutomationConfig
):
    company_id = company.get("companyId")
    company_name = company.get("name", "Unknown Company")

    print(f"\n  [{company_id}] Processing: {company_name}")

    try:
        address = company.get("primaryAddress", {}).get("name", "null")
        company_phone = company.get("primaryAddress", {}).get("phone", "null")

        # Extract main contact information
        try:
            main_contact = company.get("mainContact", {})
            first_name_contact = main_contact.get("firstName", "null")
            email = main_contact.get("email", "null")
            phone = main_contact.get("phone", "null")
        except Exception:
            first_name_contact = "null"
            email = "null"
            phone = "null"

        # Validation 1: Check if company has contact information
        if phone == "null" and email == "null":
            print(f"  ❌ Skipping: No contact info (phone: {phone}, email: {email})")
            return
        business_info = f"Company name: {company_name}\nAddress: {address}"
        hiring_data = detect_company_hiring_status(company_name, address)

        if not hiring_data:
            print("  ✗ Failed to analyze hiring status")
            return

        print(f"  ✓ AI Analysis: {hiring_data}")

        is_hiring = hiring_data.get("Is Hiring actively", "null")
        job_titles = hiring_data.get("Hiring Job Title/Position", ["null"])
        is_agency = hiring_data.get("Is agency", "null")

        # Validation 3: Check for valid job titles
        if job_titles == ["null"] or not job_titles or len(job_titles) == 0:
            print("  ❌ Skipping: No job titles found")
            return

        # Company is hiring! Proceed with opportunity creation and marketing
        print(f"  ✓ Company is hiring: {len(job_titles)} position(s)")

        # Determine contact method and contact information
        primary_contact_phone = None
        primary_contact_email = None

        if phone != "null":
            primary_contact_phone = phone.strip()
        elif company_phone != "null":
            primary_contact_phone = company_phone

        if not primary_contact_phone and email != "null":
            primary_contact_email = email

        print(
            f"  📞 Contact: Phone={primary_contact_phone}, Email={primary_contact_email}"
        )

        # Create opportunities for each job title
        opportunities_created = False
        for job_title in job_titles:
            if job_title == "null":
                continue

            # Get owner user IDs from config
            owner_user_ids = config.opportunity_owners
            success = create_opportunity(
                company_id, f"test {job_title}", owner_user_ids, config
            )
            if success:
                opportunities_created = True

        if not opportunities_created:
            print("  ✗ Failed to create any opportunities")
            return

        # Determine the job title for marketing message
        actual_job_title = None
        if len(job_titles) == 1 and job_titles[0] != "null":
            actual_job_title = job_titles[0]

        print(f"  ✓ Completed: {company_id}")

    except Exception as e:
        print(f"  ✗ Error processing company: {str(e)}")


@shared_task
def run_marketing_automation_for_organization(organization_id: int):
    print(f"\n{'=' * 80}")
    print(f"Marketing Automation - Organization: {organization_id}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 80}\n")

    try:
        config = MarketingAutomationConfig.objects.get(
            organization_id=organization_id, is_active=True
        )
    except MarketingAutomationConfig.DoesNotExist:
        print(f"✗ No active marketing automation config for org {organization_id}")
        return

    print("\n[Step 1] Fetching companies...")
    companies = fetch_all_companies(config)

    if not companies:
        print("✗ No companies found")
        return

    print(f"\n[Step 2] Processing {len(companies)} companies...")

    for idx, company in enumerate(companies, 1):
        print(f"\n{'─' * 80}")
        print(f"[{idx}/{len(companies)}]")
        process_company_for_marketing(company, config)
        time.sleep(2)  # Rate limiting

    print(f"\n{'=' * 80}")
    print(f"✓ Completed: Organization {organization_id}")
    print(f"{'=' * 80}\n")


@shared_task
def initiate_marketing_automation_for_all_organizations():
    print("\n[Task Initiated] Marketing Automation for All Organizations")

    subscribed_org_ids = Subscription.objects.filter(available_limit__gt=0).values_list(
        "organization_id", flat=True
    )

    print(f"Found {len(subscribed_org_ids)} subscribed organizations")

    for org_id in subscribed_org_ids:
        print(f"\nQueuing organization {org_id} for marketing automation")
        run_marketing_automation_for_organization.delay(org_id)

    print("\n✓ All organizations queued for marketing automation")
