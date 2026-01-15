import json
import os
import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from celery import shared_task
from dotenv import load_dotenv
from jsonschema import Draft202012Validator
from openai import OpenAI
from django.utils import timezone

from ai_lead_generation.models import MarketingAutomationConfig, MarketingAutomationReport
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


def get_all_instructions() -> Tuple[str, str]:
    """
    Returns system and user instructions for AI-based hiring detection.

    Returns:
        Tuple of (system_instructions, user_instructions_template)
    """
    SYSTEM_INSTRUCTIONS = (
        "You are an information extraction engine. Your task is to check online if a specific company is actively hiring or searching for candidates.\n"
        "Task: From the given Company details (Company name, category, address), check if they are actively hiring and collect job titles.\n"
        "Search briefly on:\n"
        "1) Indeed UK  2) LinkedIn  3) Reed  4) Carejet  5) Talent.com  6) CV-Library  7) Caterer  8) Jobicy  9) Company careers page\n"
        "- Only return verified findings from searches. Do not hallucinate.\n"
        '- For any missing/undetermined field, return the literal string "null" (not JSON null).\n'
        '- For "Is Hiring actively": return "Yes" if there is clear evidence of open roles; "No" if clear evidence of none; otherwise "null".\n'
        '- For "Hiring Job Title/Position": return a LIST of concise job titles (e.g., ["Electrician", "HGV Class 1 Driver", "Transport Planner"]). '
        'If no titles found, return ["null"]. Avoid duplicates; cap the list at 10 items.\n'
        '- For "Is agency": return "Yes" if it is a recruitment agency; "No" otherwise; "null" if unknown.\n'
        "Return ONLY raw JSON (no markdown) with this structure:\n"
        "{\n"
        '  "Is Hiring actively": "null",\n'
        '  "Hiring Job Title/Position": ["null"],\n'
        '  "Is agency": "null"\n'
        "}\n"
    )

    USER_INSTRUCTIONS_TEMPLATE = (
        "Extract whether the company is actively hiring and list job titles.\n"
        'For any field not present, output the literal string "null".\n'
        "Return ONLY raw JSON matching the specified structure (no markdown, no extra text).\n\n"
        "Info TEXT START\n"
        "{text}\n"
        "Info TEXT END\n"
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
    company_name: str, company_address: str, report: MarketingAutomationReport
) -> Optional[Dict[str, Any]]:
    """
    Use AI to detect if a company is actively hiring.

    Args:
        company_name: Name of the company
        company_address: Address/location of the company
        report: Report instance to track API calls

    Returns:
        Dictionary with hiring status, job titles, and agency status, or None on error
    """
    try:
        SCHEMA = return_Schema()
        SYSTEM_INSTRUCTIONS, USER_INSTRUCTIONS_TEMPLATE = get_all_instructions()

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

        # Track API call
        report.ai_api_calls += 1
        report.save(update_fields=['ai_api_calls'])

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


def fetch_all_companies(
    config: MarketingAutomationConfig, report: MarketingAutomationReport
) -> List[Dict[str, Any]]:
    """
    Fetch companies from the platform API.
    
    Args:
        config: Marketing automation configuration
        report: Report instance to track API calls
    
    Returns:
        List of company dictionaries
    """
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

        # Track API call
        report.platform_api_calls += 1
        report.save(update_fields=['platform_api_calls'])

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.get(
                    companies_url, headers=headers, params=params, timeout=30
                )
                report.platform_api_calls += 1
                report.save(update_fields=['platform_api_calls'])

        if response.status_code == 200:
            companies = response.json().get("items", [])
            print(f"✓ Fetched {len(companies)} companies")
            
            # Update report
            report.total_companies_fetched = len(companies)
            report.save(update_fields=['total_companies_fetched'])
            
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
    report: MarketingAutomationReport,
) -> bool:
    """
    Create an opportunity for a company.
    
    Args:
        company_id: ID of the company
        job_title: Job title for the opportunity
        owner_user_ids: List of owner user IDs
        config: Marketing automation configuration
        report: Report instance to track metrics
    
    Returns:
        True if successful, False otherwise
    """
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

        # Track API call
        report.platform_api_calls += 1
        report.save(update_fields=['platform_api_calls'])

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.post(
                    opportunities_url, json=payload, headers=headers, timeout=30
                )
                report.platform_api_calls += 1
                report.save(update_fields=['platform_api_calls'])

        if response.status_code in [200, 201]:
            opportunity_id = response.json().get("opportunityId")
            print(f"    ✓ Created opportunity: {job_title} (ID: {opportunity_id})")
            
            # Update report
            report.opportunities_created += 1
            report.add_job_title(job_title)
            report.save(update_fields=['opportunities_created', 'job_titles_found'])
            
            return True

        print(f"    ✗ Failed to create opportunity: {response.status_code}")
        report.opportunities_failed += 1
        report.save(update_fields=['opportunities_failed'])
        return False

    except Exception as e:
        print(f"    ✗ Error creating opportunity: {str(e)}")
        report.opportunities_failed += 1
        report.save(update_fields=['opportunities_failed'])
        return False


def process_company_for_marketing(
    company: Dict[str, Any],
    config: MarketingAutomationConfig,
    report: MarketingAutomationReport,
):
    """
    Process a single company for marketing automation.
    
    Args:
        company: Company data dictionary
        config: Marketing automation configuration
        report: Report instance to track metrics
    """
    company_id = company.get("companyId")
    company_name = company.get("name", "Unknown Company")

    print(f"\n  [{company_id}] Processing: {company_name}")

    try:
        # Track that we're processing this company
        report.companies_processed += 1
        report.save(update_fields=['companies_processed'])

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
            report.companies_skipped += 1
            report.skipped_no_contact += 1
            report.save(update_fields=['companies_skipped', 'skipped_no_contact'])
            return

        # Analyze hiring status
        hiring_data = detect_company_hiring_status(company_name, address, report)

        if not hiring_data:
            print("  ✗ Failed to analyze hiring status")
            report.companies_failed += 1
            report.save(update_fields=['companies_failed'])
            return

        print(f"  ✓ AI Analysis: {hiring_data}")

        is_hiring = hiring_data.get("Is Hiring actively", "null")
        job_titles = hiring_data.get("Hiring Job Title/Position", ["null"])
        is_agency = hiring_data.get("Is agency", "null")

        # Track agency detection
        if is_agency == "Yes":
            report.agencies_detected += 1
            report.save(update_fields=['agencies_detected'])
            
            # Check if we should exclude agencies
            if config.exclude_agencies:
                print("  ❌ Skipping: Company is a recruitment agency")
                report.companies_skipped += 1
                report.agencies_excluded += 1
                report.save(update_fields=['companies_skipped', 'agencies_excluded'])
                return

        # Check if company is hiring
        if is_hiring != "Yes":
            print(f"  ❌ Skipping: Not actively hiring (status: {is_hiring})")
            report.companies_skipped += 1
            report.skipped_no_hiring += 1
            report.save(update_fields=['companies_skipped', 'skipped_no_hiring'])
            return

        # Validation 3: Check for valid job titles
        if job_titles == ["null"] or not job_titles or len(job_titles) == 0:
            print("  ❌ Skipping: No job titles found")
            report.companies_skipped += 1
            report.skipped_no_job_titles += 1
            report.save(update_fields=['companies_skipped', 'skipped_no_job_titles'])
            return

        # Company is hiring! Track this
        report.companies_hiring += 1
        report.save(update_fields=['companies_hiring'])
        
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
                company_id, f"test {job_title}", owner_user_ids, config, report
            )
            if success:
                opportunities_created = True

        if opportunities_created:
            # Track company with opportunities
            report.add_company_with_opportunity(company_id)
            report.save(update_fields=['companies_with_opportunities'])
            print(f"  ✓ Completed: {company_id}")
        else:
            print("  ✗ Failed to create any opportunities")

    except Exception as e:
        print(f"  ✗ Error processing company: {str(e)}")
        report.companies_failed += 1
        report.save(update_fields=['companies_failed'])


@shared_task
def run_marketing_automation_for_organization(organization_id: int):
    """
    Run marketing automation for a specific organization and generate a report.
    
    Args:
        organization_id: ID of the organization to run automation for
    """
    print(f"\n{'=' * 80}")
    print(f"Marketing Automation - Organization: {organization_id}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 80}\n")

    # Initialize report
    report = None

    try:
        # Get configuration
        config = MarketingAutomationConfig.objects.get(
            organization_id=organization_id, is_active=True
        )
        
        # Create report
        report = MarketingAutomationReport.objects.create(
            organization_id=organization_id,
            config=config,
            status='running'
        )
        
        print(f"📊 Created report ID: {report.id}")

    except MarketingAutomationConfig.DoesNotExist:
        print(f"✗ No active marketing automation config for org {organization_id}")
        return

    try:
        # Fetch companies
        print("\n[Step 1] Fetching companies...")
        companies = fetch_all_companies(config, report)

        if not companies:
            print("✗ No companies found")
            report.mark_completed(status='completed')
            return

        print(f"\n[Step 2] Processing {len(companies)} companies...")

        # Process each company
        for idx, company in enumerate(companies, 1):
            print(f"\n{'─' * 80}")
            print(f"[{idx}/{len(companies)}]")
            process_company_for_marketing(company, config, report)
            time.sleep(2)  # Rate limiting

        # Mark report as completed
        report.mark_completed(status='completed')

        print(f"\n{'=' * 80}")
        print(f"✓ Completed: Organization {organization_id}")
        print(f"\n📊 Report Summary:")
        print(f"   - Companies Fetched: {report.total_companies_fetched}")
        print(f"   - Companies Processed: {report.companies_processed}")
        print(f"   - Companies Hiring: {report.companies_hiring}")
        print(f"   - Companies Skipped: {report.companies_skipped}")
        print(f"   - Opportunities Created: {report.opportunities_created}")
        print(f"   - Duration: {report.duration_seconds}s")
        print(f"   - Success Rate: {report.get_success_rate():.1f}%")
        print(f"{'=' * 80}\n")

    except Exception as e:
        error_msg = f"Fatal error in automation: {str(e)}"
        error_details = {
            'error': str(e),
            'traceback': traceback.format_exc(),
            'timestamp': datetime.now().isoformat()
        }
        
        print(f"\n✗ {error_msg}")
        print(f"✗ Traceback: {traceback.format_exc()}")
        
        if report:
            report.mark_failed(error_msg, error_details)


@shared_task
def initiate_marketing_automation_for_all_organizations():
    """
    Initiate marketing automation for all organizations with active subscriptions.
    """
    print("\n[Task Initiated] Marketing Automation for All Organizations")

    subscribed_org_ids = Subscription.objects.filter(
        available_limit__gt=0
    ).values_list("organization_id", flat=True)

    print(f"Found {len(subscribed_org_ids)} subscribed organizations")

    for org_id in subscribed_org_ids:
        print(f"\nQueuing organization {org_id} for marketing automation")
        run_marketing_automation_for_organization.delay(org_id)

    print("\n✓ All organizations queued for marketing automation")