import os
import time
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
from celery import shared_task
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from dotenv import load_dotenv
from openai import OpenAI

from cv_formatter.models import CVFormatterConfig, FormattedCV
from organizations.models import Organization
from subscription.models import Subscription

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PDF_FOLDER = "formatted_pdfs"

# Ensure folders exist
os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs("resume_candidates", exist_ok=True)


def extract_text_from_pdf(file_path: str) -> Optional[str]:
    """
    Extract text from PDF using multiple fallback methods.
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
        from pdf2image import convert_from_path
        import pytesseract

        pages = convert_from_path(file_path, dpi=300)
        full_text = "\n".join(pytesseract.image_to_string(img) for img in pages)
        return full_text.strip()
    except Exception as e:
        print(f"OCR failed: {e}")

    return None


def build_cv_extraction_prompt(cv_text: str, sections: List[str]) -> str:
    """
    Build dynamic prompt based on enabled sections.
    """
    base_prompt = f"""You are a senior CV formatter. Read the following CV/resume text and extract information.

CV TEXT:
{cv_text}

IMPORTANT: If this is not a professional CV/resume, return null values for all fields.

Extract and return a JSON object with the following fields:"""

    section_definitions = {
        "full_name": "full_name (string): Candidate's full name",
        "email": "email (string): Email address",
        "phone": "phone (string): Phone number",
        "address": "address (string): Full address",
        "professional_summary": "professional_summary (string): Brief professional summary",
        "professional_experience": """professional_experience (array): List of work experiences, each with:
  - job_title (string)
  - company_name (string)
  - start_date (string)
  - end_date (string)
  - position (string)
  - job_description (array of strings): Bullet points""",
        "education": """education (array): List of educational qualifications, each with:
  - degree (string)
  - major (string)
  - school_name (string)
  - start_date (string)
  - end_date (string)""",
        "skills": """skills (array): List of skills, each with:
  - skill_name (string)
  - skill_description (string)""",
        "certifications": """certifications (array): List of certifications, each with:
  - certification_name (string)
  - certification_authority (string)
  - start_date (string)
  - end_date (string)""",
        "languages": """languages (array): List of languages, each with:
  - language_name (string)
  - proficiency (string)""",
        "areas_of_expertise": """areas_of_expertise (array): List of expertise areas, each with:
  - expertise_name (string)
  - expertise_description (string)""",
        "recommendations": """recommendations (array): Areas for improvement, each with:
  - area_name (string)
  - area_description (string)""",
    }

    for section in sections:
        if section in section_definitions:
            base_prompt += f"\n- {section_definitions[section]}"

    base_prompt += "\n\nReturn ONLY a valid JSON object with these fields. Use null for missing information."

    return base_prompt


def extract_cv_data_with_openai(cv_text: str, sections: List[str]) -> Optional[Dict]:
    """
    Extract CV data using OpenAI Chat Completions API.
    """
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)

        prompt = build_cv_extraction_prompt(cv_text, sections)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional CV parser. Return only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )

        result = json.loads(response.choices[0].message.content)

        # Validate that we got actual data
        if not result.get("full_name"):
            print("No valid CV data extracted")
            return None

        return result

    except Exception as e:
        print(f"Error extracting CV data: {e}")
        return None


def render_cv_to_html(cv_data: Dict, with_logo: bool = True) -> str:
    """
    Render CV data to HTML using Jinja2 template.
    """
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader("templates"))

    if with_logo:
        template = env.get_template("cv_templates/cv_template.html")
    else:
        template = env.get_template("cv_templates/sec_cv_template.html")

    return template.render(cv_data=cv_data)


def convert_html_to_pdf(html_content: str, output_path: str) -> bool:
    """
    Convert HTML to PDF using WeasyPrint.
    """
    try:
        from weasyprint import HTML, CSS

        custom_css = """
        @page {
            margin: 0;
        }
        html, body {
            margin: 0;
            padding: 0;
            width: 100%;
        }
        .cv-container {
            margin: 0;
            padding: 0 40px 40px 40px;
            width: 100%;
            max-width: 100%;
            box-sizing: border-box;
        }
        """

        HTML(string=html_content).write_pdf(
            output_path, stylesheets=[CSS(string=custom_css)]
        )
        return True
    except Exception as e:
        print(f"Error converting HTML to PDF: {e}")
        return False


def upload_cv_to_platform(
    candidate_id: int, file_path: str, config: "CVFormatterConfig"
) -> bool:
    """
    Upload formatted CV to the recruitment platform.
    """
    try:
        access_token = config.platform.access_token

        # Platform-specific upload logic here
        # This is a placeholder - adjust based on your platform's API
        response = requests.post(
            f"{config.platform.base_url}/candidates/{candidate_id}/attachments",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            files={"file": open(file_path, "rb")},
            timeout=30,
        )

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                response = requests.post(
                    f"{config.platform.base_url}/candidates/{candidate_id}/attachments",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    files={"file": open(file_path, "rb")},
                    timeout=30,
                )

        response.raise_for_status()
        print(f"Successfully uploaded CV for candidate {candidate_id}")
        return True

    except Exception as e:
        print(f"Error uploading CV to platform: {e}")
        return False


def has_cv_been_processed(attachment_id: str, organization_id: int) -> bool:
    """
    Check if CV has already been processed.
    """
    from cv_formatter.models import FormattedCV

    return FormattedCV.objects.filter(
        attachment_id=attachment_id, organization_id=organization_id
    ).exists()


def mark_cv_as_processed(
    attachment_id: str,
    organization_id: int,
    candidate_id: int,
    status: str,
    cv_data: Optional[Dict] = None,
):
    """
    Mark CV as processed in database.
    """
    from cv_formatter.models import FormattedCV

    FormattedCV.objects.create(
        attachment_id=attachment_id,
        organization_id=organization_id,
        candidate_id=candidate_id,
        status=status,
        extracted_data=cv_data or {},
        processed_at=datetime.now(timezone.utc),
    )


@shared_task(max_retries=3)
def format_single_cv(
    attachment_id: str,
    candidate_id: int,
    candidate_name: str,
    attachment_url: str,
    file_name: str,
    organization_id: int,
):
    """
    Format a single CV for a candidate.
    """
    try:
        config = CVFormatterConfig.objects.get(organization_id=organization_id)
    except CVFormatterConfig.DoesNotExist:
        print(f"No CV formatter config found for organization {organization_id}")
        return

    # Check if already processed
    if has_cv_been_processed(attachment_id, organization_id):
        print(
            f"CV {attachment_id} already processed for organization {organization_id}"
        )
        return

    # Download CV file
    temp_file_path = f"resume_candidates/cv_{attachment_id}.pdf"

    try:
        # Download the file from platform
        access_token = config.platform.access_token
        response = requests.get(
            attachment_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            response = requests.get(
                attachment_url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30,
            )

        response.raise_for_status()

        with open(temp_file_path, "wb") as f:
            f.write(response.content)

        print(f"Downloaded CV for candidate: {candidate_name}")

    except Exception as e:
        print(f"Error downloading CV: {e}")
        mark_cv_as_processed(
            attachment_id, organization_id, candidate_id, "download_failed"
        )
        return

    # Extract text from CV
    try:
        extracted_text = extract_text_from_pdf(temp_file_path)

        if not extracted_text:
            print(f"No text extracted from CV for {candidate_name}")
            mark_cv_as_processed(
                attachment_id, organization_id, candidate_id, "extraction_failed"
            )
            os.remove(temp_file_path)
            return

    except Exception as e:
        print(f"Error extracting text: {e}")
        mark_cv_as_processed(
            attachment_id, organization_id, candidate_id, "extraction_failed"
        )
        os.remove(temp_file_path)
        return

    # Process CV with OpenAI
    try:
        enabled_sections = config.get_enabled_sections()
        cv_data = extract_cv_data_with_openai(extracted_text, enabled_sections)

        if not cv_data:
            print(f"Failed to extract CV data for {candidate_name}")
            mark_cv_as_processed(
                attachment_id, organization_id, candidate_id, "parsing_failed"
            )
            os.remove(temp_file_path)
            return

    except Exception as e:
        print(f"Error processing CV with AI: {e}")
        mark_cv_as_processed(attachment_id, organization_id, candidate_id, "ai_failed")
        os.remove(temp_file_path)
        return

    # Generate formatted PDFs
    try:
        # With logo
        html_with_logo = render_cv_to_html(cv_data, with_logo=True)
        pdf_path_with_logo = f"{PDF_FOLDER}/formatted_{file_name}_{attachment_id}.pdf"

        if not convert_html_to_pdf(html_with_logo, pdf_path_with_logo):
            raise Exception("Failed to generate PDF with logo")

        # Without logo
        html_without_logo = render_cv_to_html(cv_data, with_logo=False)
        pdf_path_without_logo = (
            f"{PDF_FOLDER}/formatted_without_logo_{file_name}_{attachment_id}.pdf"
        )

        if not convert_html_to_pdf(html_without_logo, pdf_path_without_logo):
            raise Exception("Failed to generate PDF without logo")

        print(f"Generated formatted PDFs for {candidate_name}")

    except Exception as e:
        print(f"Error generating PDFs: {e}")
        mark_cv_as_processed(
            attachment_id, organization_id, candidate_id, "pdf_generation_failed"
        )
        os.remove(temp_file_path)
        return

    # Upload to platform
    try:
        # if config.upload_with_logo:
        #     upload_cv_to_platform(candidate_id, pdf_path_with_logo, config)
        #     time.sleep(5)

        # if config.upload_without_logo:
        #     upload_cv_to_platform(candidate_id, pdf_path_without_logo, config)

        print(f"Successfully uploaded formatted CVs for {candidate_name}")

        # Mark as successfully processed
        mark_cv_as_processed(
            attachment_id, organization_id, candidate_id, "success", cv_data
        )

        # Cleanup
        os.remove(temp_file_path)
        if os.path.exists(pdf_path_with_logo):
            os.remove(pdf_path_with_logo)
        if os.path.exists(pdf_path_without_logo):
            os.remove(pdf_path_without_logo)

    except Exception as e:
        print(f"Error uploading CVs: {e}")
        mark_cv_as_processed(
            attachment_id, organization_id, candidate_id, "upload_failed", cv_data
        )
        # Still cleanup files
        os.remove(temp_file_path)
        if os.path.exists(pdf_path_with_logo):
            os.remove(pdf_path_with_logo)
        if os.path.exists(pdf_path_without_logo):
            os.remove(pdf_path_without_logo)


@shared_task
def fetch_platform_cvs(config: "CVFormatterConfig") -> List[Dict]:
    """
    Fetch CVs from the recruitment platform that need formatting.
    """
    access_token = config.platform.access_token

    if not access_token:
        print("Error: Could not get platform access token")
        return []

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    cvs_to_process = []

    try:
        # Fetch live jobs
        jobs_response = requests.get(
            f"{config.platform.base_url}/jobads", headers=headers, timeout=30
        )

        if jobs_response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                jobs_response = requests.get(
                    f"{config.platform.base_url}/jobads", headers=headers, timeout=30
                )

        jobs_response.raise_for_status()
        jobs_data = jobs_response.json()

        print(
            f"Found {len(jobs_data.get('items', []))} jobs for organization {config.organization_id}"
        )

        for job in jobs_data.get("items", []):
            # Only process jobs in specified status
            if job.get("state") != config.job_status_for_formatting:
                continue

            job_title = job.get("title")
            applications_url = job.get("links", {}).get("applications")

            if not applications_url:
                continue

            try:
                # Fetch applications
                applications_response = requests.get(
                    applications_url, headers=headers, timeout=30
                )

                if applications_response.status_code == 401:
                    access_token = config.platform.refresh_access_token()
                    if access_token:
                        headers["Authorization"] = f"Bearer {access_token}"
                        applications_response = requests.get(
                            applications_url, headers=headers, timeout=30
                        )

                applications_response.raise_for_status()
                applications_data = applications_response.json()

                for application in applications_data.get("items", []):
                    candidate = application.get("candidate", {})
                    candidate_id = candidate.get("candidateId")
                    candidate_name = f"{candidate.get('firstName', '')} {candidate.get('lastName', '')}"

                    # Fetch candidate attachments
                    attachments_url = candidate.get("links", {}).get("attachments")

                    if not attachments_url:
                        continue

                    try:
                        attachments_response = requests.get(
                            attachments_url, headers=headers, timeout=30
                        )

                        if attachments_response.status_code == 401:
                            access_token = config.platform.refresh_access_token()
                            if access_token:
                                headers["Authorization"] = f"Bearer {access_token}"
                                attachments_response = requests.get(
                                    attachments_url, headers=headers, timeout=30
                                )

                        attachments_response.raise_for_status()
                        attachments_data = attachments_response.json()

                        for attachment in attachments_data.get("items", []):
                            # Only process resumes
                            if attachment.get("category") != "Resume":
                                continue

                            attachment_id = attachment.get("attachmentId")
                            file_name = attachment.get("fileName")
                            attachment_url = attachment.get("links", {}).get("self")

                            # Check if already processed
                            if has_cv_been_processed(
                                attachment_id, config.organization_id
                            ):
                                print(f"CV {attachment_id} already processed")
                                continue

                            cv_data = {
                                "attachment_id": attachment_id,
                                "candidate_id": candidate_id,
                                "candidate_name": candidate_name,
                                "attachment_url": attachment_url,
                                "file_name": file_name,
                                "organization_id": config.organization_id,
                            }

                            cvs_to_process.append(cv_data)
                            print(f"Added CV for processing: {candidate_name}")

                    except Exception as e:
                        print(f"Error fetching attachments: {e}")
                        continue

            except Exception as e:
                print(f"Error fetching applications for job {job_title}: {e}")
                continue

        print(f"Total CVs to process: {len(cvs_to_process)}")
        return cvs_to_process

    except Exception as e:
        print(f"Error fetching platform data: {e}")
        return []


@shared_task
def bulk_format_cvs(organization_id: int = None):
    try:
        config = CVFormatterConfig.objects.get(organization_id=organization_id)
    except CVFormatterConfig.DoesNotExist:
        print(f"No CV formatter config found for organization {organization_id}")
        return

    cvs = fetch_platform_cvs(config)

    if not cvs:
        print(f"No CVs to process for organization {organization_id}")
        return

    # Queue CV formatting tasks with delays
    for i, cv in enumerate(cvs):
        countdown = i * 120
        format_single_cv.apply_async(
            args=[
                cv["attachment_id"],
                cv["candidate_id"],
                cv["candidate_name"],
                cv["attachment_url"],
                cv["file_name"],
                cv["organization_id"],
            ],
            countdown=countdown,
        )

    print(f"Queued {len(cvs)} CVs for formatting for organization {organization_id}")


@shared_task
def initiate_all_cv_formatting():
    """
    Periodic task to format CVs for all organizations.
    """
    organization_ids = Organization.objects.filter().values_list("id", flat=True)

    subscribed_organization_ids = Subscription.objects.filter(
        organization_id__in=organization_ids, available_limit__gt=0
    ).values_list("organization_id", flat=True)

    for organization_id in subscribed_organization_ids:
        print(f"Initiating CV formatting for organization {organization_id}")
        bulk_format_cvs.delay(organization_id)
