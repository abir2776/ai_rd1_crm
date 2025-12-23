import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict

import requests
from celery import shared_task
from django.utils import timezone as django_timezone
from dotenv import load_dotenv
from jsonschema import Draft202012Validator
from openai import OpenAI

from .models import LeadGenerationConfig
from subscription.models import Subscription

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API")
TEMP_RESUME_FOLDER = "resume_leads"
MODEL = "gpt-4o"

os.makedirs(TEMP_RESUME_FOLDER, exist_ok=True)


def return_lead_schema():
    """JSON schema for lead extraction"""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "companies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "Company name": {"type": "string"},
                        "Industry / Sector": {"type": "string"},
                        "Company address": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "street": {"type": "string"},
                                "city": {"type": "string"},
                                "state": {"type": "string"},
                                "postalCode": {"type": "string"},
                                "countryCode": {"type": "string"},
                                "name": {"type": "string"},
                            },
                            "required": [
                                "street",
                                "city",
                                "state",
                                "postalCode",
                                "countryCode",
                                "name",
                            ],
                        },
                        "Company Phone number (international format)": {
                            "type": "string"
                        },
                        "Company Mobile number (international format)": {
                            "type": "string"
                        },
                        "Company website (canonical URL)": {"type": "string"},
                        "LinkedIn profile URL (company or contact)": {"type": "string"},
                        "Twitter profile URL (company or contact)": {"type": "string"},
                        "Contact person name (First Last)": {"type": "string"},
                        "Contact person position": {"type": "string"},
                        "Contact phone (international format)": {"type": "string"},
                        "Contact email (work email preferred)": {"type": "string"},
                        "Is related company (Logistics, Haulage, School, Transport & Recruitment)": {
                            "type": "string",
                            "enum": ["Yes", "No", "null"],
                        },
                    },
                    "required": [
                        "Company name",
                        "Industry / Sector",
                        "Company address",
                        "Company Phone number (international format)",
                        "Company Mobile number (international format)",
                        "Company website (canonical URL)",
                        "LinkedIn profile URL (company or contact)",
                        "Twitter profile URL (company or contact)",
                        "Contact person name (First Last)",
                        "Contact person position",
                        "Contact phone (international format)",
                        "Contact email (work email preferred)",
                        "Is related company (Logistics, Haulage, School, Transport & Recruitment)",
                    ],
                },
            },
            "Contacts in CV": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "person_name": {"type": "string"},
                        "phone_or_mobile": {"type": "string"},
                        "company_name": {"type": "string"},
                    },
                    "required": ["person_name", "phone_or_mobile", "company_name"],
                },
            },
        },
        "required": ["companies", "Contacts in CV"],
    }


def get_lead_instructions():
    """System and user instructions for lead extraction"""
    SYSTEM = (
        "You are an information extraction engine. Extract company and contact details from CV text.\n"
        "- List every company the candidate worked with (past and present)\n"
        "- Merge multiple roles at same company into one entry\n"
        "- Extract ONLY explicit information; do NOT invent data\n"
        '- Return "null" string for missing fields (not JSON null)\n'
        "- For 'Is related company': Return 'Yes' if Logistics/Haulage/School/Transport/Recruitment, else 'No', or 'null' if uncertain\n"
        "- For 'Contacts in CV': Extract contacts mentioned (excluding CV owner)\n"
        "- Return ONLY raw JSON (no markdown fences)"
    )

    USER = (
        "Extract company and contact details.\n"
        'For missing fields, output "null".\n'
        "Return ONLY raw JSON.\n\n"
        "CV TEXT START\n{cv_text}\nCV TEXT END\n"
    )

    return SYSTEM, USER


def strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.strip("`").strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()
    return s


def find_json_block(s: str) -> str:
    s = s.strip()
    obj_match = re.search(r"\{.*\}\s*$", s, flags=re.DOTALL)
    if obj_match:
        return obj_match.group(0)
    return s


def normalize_nulls(data: Dict[str, Any]) -> Dict[str, Any]:
    def to_str_null(v: Any) -> str:
        if v is None or (isinstance(v, str) and not v.strip()):
            return "null"
        return str(v).strip() if isinstance(v, str) else str(v)

    for cd in data.get("Contacts in CV", []):
        for k in ["person_name", "phone_or_mobile", "company_name"]:
            cd[k] = to_str_null(cd.get(k))

    for c in data.get("companies", []):
        for k in [
            "Company name",
            "Industry / Sector",
            "Company Phone number (international format)",
            "Company Mobile number (international format)",
            "Company website (canonical URL)",
            "LinkedIn profile URL (company or contact)",
            "Twitter profile URL (company or contact)",
            "Contact person name (First Last)",
            "Contact person position",
            "Contact phone (international format)",
            "Contact email (work email preferred)",
            "Is related company (Logistics, Haulage, School, Transport & Recruitment)",
        ]:
            c[k] = to_str_null(c.get(k))

        addr = c.get("Company address", {})
        if not isinstance(addr, dict):
            addr = {}
        for ak in ["street", "city", "state", "postalCode", "countryCode", "name"]:
            addr[ak] = to_str_null(addr.get(ak))
        c["Company address"] = addr

    return data


def extract_text_from_pdf(file_path: str) -> str:
    try:
        import fitz

        doc = fitz.open(file_path)
        text = []
        for page in doc:
            text.append(page.get_text("text"))
        if text and "".join(text).strip():
            return "\n".join(text)
    except:
        pass

    try:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            pages_text = [p.extract_text() or "" for p in pdf.pages]
        if any(pages_text):
            return "\n".join(pages_text)
    except:
        pass

    try:
        from pypdf import PdfReader

        reader = PdfReader(file_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except:
        pass

    return ""


def extract_companies_and_contacts_from_resume(resume_text: str) -> dict:
    try:
        SCHEMA = return_lead_schema()
        SYSTEM, USER = get_lead_instructions()

        client = OpenAI(api_key=OPENAI_API_KEY)

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": USER.format(cv_text=resume_text)},
            ],
        )

        raw = response.choices[0].message.content or ""
        content = strip_code_fences(raw)

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            candidate = find_json_block(content)
            data = json.loads(candidate)

        Draft202012Validator(SCHEMA).validate(data)
        data = normalize_nulls(data)

        companies = data.get("companies", [])
        contacts = data.get("Contacts in CV", [])

        print(f"  ✓ Extracted {len(companies)} companies and {len(contacts)} contacts")
        return data

    except Exception as e:
        print(f"  ✗ Error extracting: {str(e)}")
        return {"companies": [], "Contacts in CV": []}


def fetch_formatted_resume(candidate_id: int, config: LeadGenerationConfig) -> str:
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
            return ""

        attachments = response.json().get("items", [])
        if not attachments:
            return ""

        first_resume = attachments[0]
        attachment_id = first_resume.get("attachmentId")
        resume_url = first_resume.get("url") or first_resume.get("links", {}).get(
            "self"
        )

        if not resume_url:
            return ""

        temp_file_path = f"{TEMP_RESUME_FOLDER}/lead_{candidate_id}_{attachment_id}.pdf"

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
            return ""

        with open(temp_file_path, "wb") as f:
            f.write(resume_response.content)

        resume_text = extract_text_from_pdf(temp_file_path)

        # Delete CV immediately after extraction
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            print(f"  ✓ Deleted CV file")

        return resume_text

    except Exception as e:
        print(f"  ✗ Error fetching resume: {str(e)}")
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass
        return ""


def check_company_exists(company_name: str, config: LeadGenerationConfig) -> tuple:
    try:
        access_token = config.platform.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        search_url = f"{config.platform.base_url}/companies"
        params = {"Name": company_name}

        response = requests.get(search_url, headers=headers, params=params, timeout=30)

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.get(
                    search_url, headers=headers, params=params, timeout=30
                )

        if response.status_code == 200:
            companies = response.json().get("items", [])
            if companies:
                return True, companies[0].get("companyId")

        return False, None
    except:
        return False, None


def create_company_in_jobadder(company_data: dict, config: LeadGenerationConfig) -> int:
    try:
        access_token = config.platform.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        company_url = f"{config.platform.base_url}/companies"

        payload = {"name": company_data.get("Company name").strip()}

        if (
            company_data.get("Industry / Sector")
            and company_data.get("Industry / Sector") != "null"
        ):
            payload["summary"] = company_data.get("Industry / Sector").strip()

        social = {}
        linkedin = company_data.get("LinkedIn profile URL (company or contact)")
        if linkedin and linkedin != "null" and linkedin.strip():
            social["linkedin"] = linkedin.strip()

        twitter = company_data.get("Twitter profile URL (company or contact)")
        if twitter and twitter != "null" and twitter.strip():
            social["twitter"] = twitter.strip()

        if social:
            payload["social"] = social

        response = requests.post(company_url, json=payload, headers=headers, timeout=30)

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.post(
                    company_url, json=payload, headers=headers, timeout=30
                )

        if response.status_code in [200, 201]:
            company_id = response.json().get("companyId")
            print(
                f"    ✓ Created company: {company_data.get('Company name')} (ID: {company_id})"
            )
            return company_id

        return None
    except Exception as e:
        print(f"    ✗ Error creating company: {str(e)}")
        return None


def create_company_address(
    company_id: int, company_data: dict, config: LeadGenerationConfig
):
    try:
        access_token = config.platform.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        address_url = f"{config.platform.base_url}/companies/{company_id}/addresses"
        address_data = company_data.get("Company address", {})

        payload = {"isPrimaryAddress": True}

        if address_data.get("street") and address_data.get("street") != "null":
            payload["street"] = [address_data.get("street")]
        if address_data.get("city") and address_data.get("city") != "null":
            payload["city"] = address_data.get("city")
        if address_data.get("state") and address_data.get("state") != "null":
            payload["state"] = address_data.get("state")
        if address_data.get("postalCode") and address_data.get("postalCode") != "null":
            payload["postalCode"] = address_data.get("postalCode")
        if (
            address_data.get("countryCode")
            and address_data.get("countryCode") != "null"
        ):
            payload["countryCode"] = address_data.get("countryCode")
        if address_data.get("name") and address_data.get("name") != "null":
            payload["name"] = address_data.get("name")

        phone = company_data.get("Company Phone number (international format)")
        if phone and phone != "null":
            payload["phone"] = phone.replace(" ", "").replace("-", "")

        website = company_data.get("Company website (canonical URL)")
        if website and website != "null":
            payload["url"] = website

        response = requests.post(address_url, json=payload, headers=headers, timeout=30)

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.post(
                    address_url, json=payload, headers=headers, timeout=30
                )

        if response.status_code in [200, 201]:
            print(f"      ✓ Created address")
    except Exception as e:
        print(f"      ✗ Error creating address: {str(e)}")


def create_contact_in_jobadder(
    contact_data: dict, company_id: int, config: LeadGenerationConfig
):
    try:
        access_token = config.platform.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        contact_url = f"{config.platform.base_url}/contacts"

        full_name = contact_data.get("Contact person name (First Last)", "").strip()
        first_name, last_name = ("Unknown", "")

        if full_name and full_name != "null":
            try:
                first_name, last_name = full_name.split(" ", 1)
            except ValueError:
                first_name = full_name

        payload = {"firstName": first_name, "lastName": last_name}

        email = contact_data.get("Contact email (work email preferred)")
        if email and email != "null":
            payload["email"] = email

        phone = contact_data.get("Contact phone (international format)")
        if phone and phone != "null":
            payload["phone"] = phone.replace(" ", "").replace("-", "")

        position = contact_data.get("Contact person position")
        if position and position != "null":
            payload["position"] = position

        if company_id:
            payload["companyId"] = company_id

        response = requests.post(contact_url, json=payload, headers=headers, timeout=30)

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.post(
                    contact_url, json=payload, headers=headers, timeout=30
                )

        if response.status_code in [200, 201]:
            print(f"      ✓ Created contact: {full_name}")
    except Exception as e:
        print(f"      ✗ Error creating contact: {str(e)}")


def create_additional_contact(
    contact_data: dict, company_id: int, config: LeadGenerationConfig
):
    try:
        access_token = config.platform.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        contact_url = f"{config.platform.base_url}/contacts"

        full_name = contact_data.get("person_name", "").strip()
        first_name, last_name = ("Unknown", "")

        if full_name and full_name != "null":
            try:
                first_name, last_name = full_name.split(" ", 1)
            except ValueError:
                first_name = full_name

        payload = {"firstName": first_name, "lastName": last_name}

        phone = contact_data.get("phone_or_mobile")
        if phone and phone != "null":
            payload["phone"] = phone.replace(" ", "").replace("-", "")

        if company_id:
            payload["companyId"] = company_id

        response = requests.post(contact_url, json=payload, headers=headers, timeout=30)

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.post(
                    contact_url, json=payload, headers=headers, timeout=30
                )

        if response.status_code in [200, 201]:
            print(f"        ✓ Created contact: {full_name}")
    except Exception as e:
        print(f"        ✗ Error creating contact: {str(e)}")


def process_candidate_for_lead_generation(
    candidate: dict, config: LeadGenerationConfig
):
    candidate_id = candidate.get("candidateId")
    candidate_name = f"{candidate.get('firstName', '')} {candidate.get('lastName', '')}"

    print(f"\n  [{candidate_id}] Processing: {candidate_name}")

    try:
        resume_text = fetch_formatted_resume(candidate_id, config)

        if not resume_text:
            print(f"  ⚠ No resume content")
            return

        extracted_data = extract_companies_and_contacts_from_resume(resume_text)

        companies = extracted_data.get("companies", [])
        contacts_in_cv = extracted_data.get("Contacts in CV", [])
        print("Companies: ", companies)
        print("Contacts: ", contacts_in_cv)

        if not companies and not contacts_in_cv:
            print(f"  ⚠ No data extracted")
            return

        company_id_map = {}

        # for company in companies:
        #     company_name = company.get("Company name", "").strip()

        #     if not company_name or company_name == "null":
        #         print(f"    ❌ Missing company name, skipping")
        #         continue

        #     is_related = company.get("Is related company (Logistics, Haulage, School, Transport & Recruitment)")
        #     if is_related == "Yes":
        #         print(f"    ❌ Related company (Logistics/Haulage/etc), skipping")
        #         continue

        #     address_name = company.get("Company address", {}).get("name")
        #     if not address_name or address_name == "null":
        #         print(f"    ❌ Missing company address, skipping")
        #         continue

        #     exists, existing_id = check_company_exists(company_name, config)
        #     if exists:
        #         print(f"    ⚠ Company exists (ID: {existing_id}), skipping")
        #         continue

        #     print(f"\n    Creating: {company_name}")

        #     company_id = create_company_in_jobadder(company, config)

        #     if company_id:
        #         company_id_map[company_name] = company_id
        #         create_company_address(company_id, company, config)
        #         create_contact_in_jobadder(company, company_id, config)
        #         time.sleep(0.5)

        # for contact in contacts_in_cv:
        #     person_name = contact.get("person_name", "").strip()
        #     phone = contact.get("phone_or_mobile", "").strip()
        #     company_name = contact.get("company_name", "").strip()

        #     if not person_name or person_name == "null" or not phone or phone == "null":
        #         continue

        #     print(f"\n      Creating additional contact: {person_name}")

        #     company_id = None
        #     if company_name and company_name != "null":
        #         company_id = company_id_map.get(company_name)
        #         if not company_id:
        #             exists, existing_id = check_company_exists(company_name, config)
        #             if exists:
        #                 company_id = existing_id

        #     create_additional_contact(contact, company_id, config)
        #     time.sleep(0.5)

        print(f"\n  ✓ Completed: {candidate_id}")

    except Exception as e:
        print(f"  ✗ Error: {str(e)}")


def fetch_all_candidates(config: LeadGenerationConfig) -> list:
    access_token = config.platform.access_token

    if not access_token:
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
                access_token = config.platform.refresh_access_token()
                if not access_token:
                    return all_candidates
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.get(
                    candidates_url, headers=headers, params=params, timeout=30
                )

            response.raise_for_status()
            items = response.json().get("items", [])

            if not items:
                break

            print(f"Fetched: offset={offset}, count={len(items)}")
            all_candidates.extend(items)

            if len(items) < limit:
                break

            offset += limit
            time.sleep(1)

        print(f"✓ Total candidates: {len(all_candidates)}")
        return all_candidates

    except Exception as e:
        print(f"✗ Error fetching candidates: {str(e)}")
        return all_candidates


@shared_task
def run_ai_lead_generation_for_organization(organization_id: int):
    print(f"\n{'=' * 80}")
    print(f"AI Client Lead Generation - Org: {organization_id}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 80}\n")

    try:
        config = LeadGenerationConfig.objects.get(
            organization_id=organization_id, is_active=True
        )
    except LeadGenerationConfig.DoesNotExist:
        print(f"✗ No active config for org {organization_id}")
        return

    print("\n[Step 1] Fetching candidates...")
    candidates = fetch_all_candidates(config)

    if not candidates:
        print("✗ No candidates found")
        return

    print(f"\n[Step 2] Processing {len(candidates)} candidates...")

    for idx, candidate in enumerate(candidates, 1):
        print(f"\n{'─' * 80}")
        print(f"[{idx}/{len(candidates)}]")
        process_candidate_for_lead_generation(candidate, config)
        time.sleep(2)

    print(f"\n{'=' * 80}")
    print(f"✓ Completed: org {organization_id}")
    print(f"{'=' * 80}\n")


@shared_task
def initiate_ai_lead_generation_for_all_organizations():
    print("\n[Task Initiated] AI Lead Generation for All Organizations")

    subscribed_org_ids = Subscription.objects.filter(available_limit__gt=0).values_list(
        "organization_id", flat=True
    )

    print(f"Found {len(subscribed_org_ids)} subscribed organizations")

    for org_id in subscribed_org_ids:
        print(f"\nQueuing org {org_id}")
        run_ai_lead_generation_for_organization.delay(org_id)

    print("\n✓ All organizations queued")
