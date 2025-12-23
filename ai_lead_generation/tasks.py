import json
import os
import time
from datetime import datetime

import requests
from celery import shared_task
from dotenv import load_dotenv
from openai import OpenAI

from subscription.models import Subscription

from .models import LeadGenerationConfig

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API")
TEMP_RESUME_FOLDER = "resume_leads"

# Ensure folder exists
os.makedirs(TEMP_RESUME_FOLDER, exist_ok=True)


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from PDF using multiple fallback methods.
    Same as CV formatter implementation.
    """
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(file_path)
        text = []
        for page in doc:
            text.append(page.get_text("text"))
        if text and "".join(text).strip():
            return "\n".join(text)
    except Exception as e:
        print(f"PyMuPDF failed: {e}")

    try:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages]
        if any(pages_text):
            return "\n".join(pages_text)
    except Exception as e:
        print(f"pdfplumber failed: {e}")

    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        all_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return all_text.strip()
    except Exception as e:
        print(f"pypdf failed: {e}")

    try:
        import pytesseract
        from pdf2image import convert_from_path

        pages = convert_from_path(file_path, dpi=300)
        full_text = "\n".join(pytesseract.image_to_string(img) for img in pages)
        return full_text.strip()
    except Exception as e:
        print(f"OCR failed: {e}")

    return ""


def get_system_instructions_for_lead_extraction():
    """System instructions for extracting companies and contacts from resume"""
    return """You are an AI assistant specialized in extracting company and contact information from resumes for lead generation purposes.

Your task is to analyze a candidate's resume and extract:
1. All companies where the candidate has worked (past employers)
2. Contact persons mentioned in the resume (references, supervisors, managers, colleagues)
3. Complete address information for each company if available
4. Contact details (email, phone, LinkedIn, etc.)

Return the data in the following JSON structure:
{
  "companies": [
    {
      "name": "Company Name",
      "legal_name": "Legal Company Name (if different)",
      "summary": "Brief description of the company or what the candidate did there",
      "address": {
        "street": ["Street line 1", "Street line 2"],
        "city": "City",
        "state": "State/Province",
        "postal_code": "Postal Code",
        "country_code": "US",
        "phone": "+1234567890",
        "url": "https://company.com"
      },
      "social": {
        "facebook": "https://www.facebook.com/company",
        "twitter": "https://twitter.com/company",
        "linkedin": "https://www.linkedin.com/company/company-name"
      }
    }
  ],
  "contacts": [
    {
      "first_name": "John",
      "last_name": "Doe",
      "email": "john.doe@company.com",
      "phone": "+1234567890",
      "mobile": "+1234567890",
      "position": "Manager",
      "company_name": "Company Name",
      "summary": "Reference - Former Manager at XYZ Corp",
      "social": {
        "linkedin": "https://www.linkedin.com/in/johndoe"
      }
    }
  ]
}

IMPORTANT EXTRACTION RULES:
1. Only extract information that is EXPLICITLY stated in the resume
2. Do NOT invent or guess information
3. If a field is not available, omit it from the JSON completely
4. Ensure all URLs are properly formatted with https://
5. Match contacts to their respective companies using the company_name field
6. Country codes should be 2-letter ISO codes (US, GB, CA, AU, etc.)
7. For companies: Extract from work experience section
8. For contacts: Look for references, supervisors mentioned, or professional contacts
9. Phone numbers should include country code (e.g., +1 for US, +44 for UK)
10. Extract company websites from the resume if mentioned

WHAT TO EXTRACT:
- Company names from employment history
- Company locations (city, state, country)
- Company websites if mentioned
- Supervisor/Manager names if mentioned
- Reference contacts with their details
- LinkedIn profiles if shared
- Email addresses if provided
- Phone numbers if provided

WHAT NOT TO DO:
- Do not extract the candidate's own information as a contact
- Do not create fake contact information
- Do not guess company addresses
- Do not invent social media URLs
- If no contacts are mentioned, return empty contacts array
- If company details are minimal, only include what's available"""


def extract_companies_and_contacts_from_resume(resume_text: str) -> dict:
    """Use GPT-4 to extract companies and contacts from resume text"""
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)

        messages = [
            {
                "role": "system",
                "content": get_system_instructions_for_lead_extraction(),
            },
            {
                "role": "user",
                "content": f"Please extract all companies and contacts from this resume for lead generation purposes:\n\n{resume_text}",
            },
        ]

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or ""

        # Remove code fences if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        data = json.loads(content.strip())

        companies = data.get("companies", [])
        contacts = data.get("contacts", [])

        print(
            f"  ✓ Extracted {len(companies)} companies and {len(contacts)} contacts from resume"
        )
        return {"companies": companies, "contacts": contacts}

    except Exception as e:
        print(f"  ✗ Error extracting companies/contacts from resume: {str(e)}")
        import traceback

        traceback.print_exc()
        return {"companies": [], "contacts": []}


def fetch_formatted_resume(candidate_id: int, config: LeadGenerationConfig) -> tuple:
    """
    Fetch the formatted resume for a candidate and extract text.
    Returns: (resume_text, temp_file_path)
    """
    temp_file_path = None
    try:
        access_token = config.platform.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        attachments_url = (
            f"{config.platform.base_url}/candidates/{candidate_id}/attachments"
        )
        params = {"Type": "FormattedResume"}

        response = requests.get(
            attachments_url, headers=headers, params=params, timeout=30
        )

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.get(
                    attachments_url, headers=headers, params=params, timeout=30
                )

        if response.status_code not in [200, 201]:
            print(f"  ✗ No formatted resume found for candidate {candidate_id}")
            return "", None

        attachments = response.json().get("items", [])
        if not attachments:
            print(f"  ✗ No formatted resume attachments for candidate {candidate_id}")
            return "", None

        # Get the first formatted resume
        first_resume = attachments[0]
        attachment_id = first_resume.get("attachmentId")
        resume_url = first_resume.get("url") or first_resume.get("links", {}).get(
            "self"
        )

        if not resume_url:
            print(f"  ✗ No URL for formatted resume of candidate {candidate_id}")
            return "", None

        # Download the resume file
        temp_file_path = (
            f"{TEMP_RESUME_FOLDER}/lead_resume_{candidate_id}_{attachment_id}.pdf"
        )

        resume_response = requests.get(
            resume_url, headers={"Authorization": f"Bearer {access_token}"}, timeout=30
        )

        if resume_response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                resume_response = requests.get(
                    resume_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30,
                )

        if resume_response.status_code != 200:
            print(f"  ✗ Failed to download resume for candidate {candidate_id}")
            return "", None

        # Save the PDF temporarily
        with open(temp_file_path, "wb") as f:
            f.write(resume_response.content)

        print(f"  ✓ Downloaded formatted resume for candidate {candidate_id}")

        # Extract text from PDF
        resume_text = extract_text_from_pdf(temp_file_path)

        if resume_text:
            print(f"  ✓ Extracted text from resume ({len(resume_text)} characters)")
        else:
            print("  ✗ Could not extract text from resume")

        # Delete the CV file immediately after extraction
        try:
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                print("  ✓ Deleted temporary CV file")
        except Exception as e:
            print(f"  ⚠ Could not delete CV file: {str(e)}")

        return resume_text, None

    except Exception as e:
        print(f"  ✗ Error fetching formatted resume: {str(e)}")
        import traceback

        traceback.print_exc()
        return "", temp_file_path


def create_company_in_jobadder(company_data: dict, config: LeadGenerationConfig) -> int:
    """Create a company in JobAdder"""
    try:
        access_token = config.platform.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        company_url = f"{config.platform.base_url}/companies"

        # Prepare company payload
        company_payload = {
            "name": company_data.get("name"),
        }

        # Add optional fields if present
        if company_data.get("legal_name"):
            company_payload["legalName"] = company_data.get("legal_name")

        if company_data.get("summary"):
            company_payload["summary"] = company_data.get("summary")

        if company_data.get("social"):
            company_payload["social"] = company_data.get("social")

        response = requests.post(
            company_url, json=company_payload, headers=headers, timeout=30
        )

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.post(
                    company_url, json=company_payload, headers=headers, timeout=30
                )

        if response.status_code in [200, 201]:
            company_response = response.json()
            company_id = company_response.get("companyId")
            print(
                f"    ✓ Created company: {company_data.get('name')} (ID: {company_id})"
            )
            return company_id
        else:
            print(
                f"    ✗ Failed to create company: {company_data.get('name')} - Status: {response.status_code}"
            )
            if response.text:
                print(f"    Response: {response.text[:200]}")
            return None

    except Exception as e:
        print(f"    ✗ Error creating company: {str(e)}")
        return None


def create_company_address(
    company_id: int, address_data: dict, config: LeadGenerationConfig
) -> bool:
    """Create address for a company in JobAdder"""
    try:
        access_token = config.platform.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        address_url = f"{config.platform.base_url}/companies/{company_id}/addresses"

        # Prepare address payload
        address_payload = {}

        if address_data.get("street"):
            address_payload["street"] = address_data.get("street")
        if address_data.get("city"):
            address_payload["city"] = address_data.get("city")
        if address_data.get("state"):
            address_payload["state"] = address_data.get("state")
        if address_data.get("postal_code"):
            address_payload["postalCode"] = address_data.get("postal_code")
        if address_data.get("country_code"):
            address_payload["countryCode"] = address_data.get("country_code")
        if address_data.get("phone"):
            address_payload["phone"] = address_data.get("phone")
        if address_data.get("url"):
            address_payload["url"] = address_data.get("url")

        address_payload["isPrimaryAddress"] = True

        response = requests.post(
            address_url, json=address_payload, headers=headers, timeout=30
        )

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.post(
                    address_url, json=address_payload, headers=headers, timeout=30
                )

        if response.status_code in [200, 201]:
            print(f"      ✓ Created address for company {company_id}")
            return True
        else:
            print(f"      ✗ Failed to create address - Status: {response.status_code}")
            return False

    except Exception as e:
        print(f"      ✗ Error creating company address: {str(e)}")
        return False


def create_contact_in_jobadder(
    contact_data: dict, company_id: int, config: LeadGenerationConfig
) -> int:
    """Create a contact in JobAdder"""
    try:
        access_token = config.platform.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        contact_url = f"{config.platform.base_url}/contacts"

        # Prepare contact payload
        contact_payload = {
            "firstName": contact_data.get("first_name", ""),
            "lastName": contact_data.get("last_name", ""),
        }

        # Add optional fields
        if contact_data.get("email"):
            contact_payload["email"] = contact_data.get("email")
        if contact_data.get("phone"):
            contact_payload["phone"] = contact_data.get("phone")
        if contact_data.get("mobile"):
            contact_payload["mobile"] = contact_data.get("mobile")
        if contact_data.get("position"):
            contact_payload["position"] = contact_data.get("position")
        if contact_data.get("summary"):
            contact_payload["summary"] = contact_data.get("summary")
        if contact_data.get("social"):
            contact_payload["social"] = contact_data.get("social")

        # Link to company if company_id is provided
        if company_id:
            contact_payload["companyId"] = company_id

        response = requests.post(
            contact_url, json=contact_payload, headers=headers, timeout=30
        )

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.post(
                    contact_url, json=contact_payload, headers=headers, timeout=30
                )

        if response.status_code in [200, 201]:
            contact_response = response.json()
            contact_id = contact_response.get("contactId")
            contact_name = f"{contact_data.get('first_name', '')} {contact_data.get('last_name', '')}"
            print(f"      ✓ Created contact: {contact_name} (ID: {contact_id})")
            return contact_id
        else:
            print(f"      ✗ Failed to create contact - Status: {response.status_code}")
            if response.text:
                print(f"      Response: {response.text[:200]}")
            return None

    except Exception as e:
        print(f"      ✗ Error creating contact: {str(e)}")
        return None


def process_candidate_for_lead_generation(
    candidate: dict, config: LeadGenerationConfig
):
    """Process a single candidate for lead generation"""
    candidate_id = candidate.get("candidateId")
    candidate_name = f"{candidate.get('firstName', '')} {candidate.get('lastName', '')}"

    print(f"\n  [{candidate_id}] Processing candidate: {candidate_name}")

    try:
        # Step 1: Fetch formatted resume and extract text
        # Note: CV file is deleted immediately after text extraction in fetch_formatted_resume
        resume_text, _ = fetch_formatted_resume(candidate_id, config)

        if not resume_text:
            print(f"  ⚠ No resume content available for candidate {candidate_id}")
            return

        # Step 2: Extract companies and contacts using AI
        extracted_data = extract_companies_and_contacts_from_resume(resume_text)

        companies = extracted_data.get("companies", [])
        contacts = extracted_data.get("contacts", [])

        if not companies and not contacts:
            print("  ⚠ No companies or contacts extracted from resume")
            return

        # Step 3: Create companies and their addresses
        company_id_map = {}  # Map company names to their IDs
        print("Companies: ", companies)
        print("Contacts: ", contacts)

        # for company in companies:
        #     company_name = company.get("name")
        #     print(f"\n    Creating company: {company_name}")

        #     company_id = create_company_in_jobadder(company, config)

        #     if company_id:
        #         company_id_map[company_name] = company_id

        #         # Create address for the company
        #         if company.get("address"):
        #             create_company_address(company_id, company.get("address"), config)

        #         time.sleep(0.5)  # Rate limiting

        # # Step 4: Create contacts and link them to companies
        # for contact in contacts:
        #     contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}"
        #     print(f"\n      Creating contact: {contact_name}")

        #     # Find the company ID for this contact
        #     company_id = None
        #     contact_company_name = contact.get("company_name")

        #     if contact_company_name and contact_company_name in company_id_map:
        #         company_id = company_id_map[contact_company_name]
        #         print(f"        → Linking to company: {contact_company_name} (ID: {company_id})")

        #     create_contact_in_jobadder(contact, company_id, config)
        #     time.sleep(0.5)  # Rate limiting

        print(f"\n  ✓ Completed lead generation for candidate {candidate_id}")

    except Exception as e:
        print(f"  ✗ Error processing candidate {candidate_id}: {str(e)}")
        import traceback

        traceback.print_exc()


def fetch_all_candidates_for_lead_generation(config: LeadGenerationConfig) -> list:
    """Fetch all candidates with pagination"""
    access_token = config.platform.access_token

    if not access_token:
        print("Error: Could not get JobAdder access token")
        return []

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    all_candidates = []
    limit = 100
    offset = 0

    try:
        candidates_url = f"{config.platform.base_url}/candidates"

        while True:
            params = {"Limit": limit, "Offset": offset}
            response = requests.get(
                candidates_url, headers=headers, params=params, timeout=30
            )

            if response.status_code == 401:
                print("Access token expired, refreshing...")
                access_token = config.platform.refresh_access_token()
                if not access_token:
                    print("Error: Could not refresh access token")
                    return all_candidates

                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.get(
                    candidates_url, headers=headers, params=params, timeout=30
                )

            response.raise_for_status()
            candidates_data = response.json()
            items = candidates_data.get("items", [])

            if not items:
                print("No more candidates to fetch")
                break

            print(f"Fetched batch: offset={offset}, count={len(items)}")
            all_candidates.extend(items)

            if len(items) < limit:
                print("Reached last page of results")
                break

            offset += limit
            time.sleep(1)  # Rate limiting between pages

        print(f"✓ Total candidates fetched: {len(all_candidates)}")
        return all_candidates

    except Exception as e:
        print(f"✗ Error fetching candidates: {str(e)}")
        return all_candidates


@shared_task
def run_ai_lead_generation_for_organization(organization_id: int):
    """Main task to run AI lead generation for an organization"""
    print(f"\n{'=' * 80}")
    print("AI Client Lead Generation")
    print(f"Organization ID: {organization_id}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 80}\n")

    try:
        config = LeadGenerationConfig.objects.get(
            organization_id=organization_id, is_active=True
        )
    except LeadGenerationConfig.DoesNotExist:
        print(f"✗ No active configuration for organization {organization_id}")
        return

    # Fetch all candidates
    print("\n[Step 1] Fetching all candidates...")
    candidates = fetch_all_candidates_for_lead_generation(config)

    if not candidates:
        print("✗ No candidates found")
        return

    # Process each candidate
    print(f"\n[Step 2] Processing {len(candidates)} candidates for lead generation...")

    total_processed = 0
    total_companies = 0
    total_contacts = 0

    for idx, candidate in enumerate(candidates, 1):
        print(f"\n{'─' * 80}")
        print(f"[{idx}/{len(candidates)}]")

        process_candidate_for_lead_generation(candidate, config)
        total_processed += 1
        break

        # Rate limiting between candidates
        time.sleep(2)

    print(f"\n{'=' * 80}")
    print(f"✓ Lead generation completed for organization {organization_id}")
    print(f"  - Candidates processed: {total_processed}")
    print(f"{'=' * 80}\n")


@shared_task
def initiate_ai_lead_generation_for_all_organizations():
    """Initiate lead generation for all subscribed organizations"""
    print("\n[Task Initiated] AI Lead Generation for All Organizations")

    subscribed_organization_ids = Subscription.objects.filter(
        available_limit__gt=0,
    ).values_list("organization_id", flat=True)

    print(f"Found {len(subscribed_organization_ids)} subscribed organizations")

    for org_id in subscribed_organization_ids:
        print(f"\nQueuing lead generation for organization {org_id}")
        run_ai_lead_generation_for_organization.delay(org_id)

    print("\n✓ All organizations queued for lead generation")
