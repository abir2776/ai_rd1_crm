# tasks.py
import json
import os
import time
from datetime import datetime

import requests
from celery import shared_task
from django.utils import timezone as django_timezone
from dotenv import load_dotenv
from jsonschema import Draft202012Validator
from openai import OpenAI

from ai_skill_search.collection_skills import get_skills_collection
from ai_skill_search.models import (
    AISkillSearchConfig,
    CandidateSkillMatch,
    JobSkillCache,
)
from ai_skill_search.utils import (
    find_json_block,
    get_all_instructions_compare_employment,
    get_all_instructions_require_skills,
    get_instructions_nearby_cities,
    return_Schema_acquired_skills,
    return_Schema_require_skills,
    strip_code_fences,
)

from .cv_skills_extraction import cv_skills_extraction

load_dotenv()

BASE_API_URL = os.getenv("CALLING_BASE_URL", "https://chatbot.rd1.co.uk")
OPENAI_API_KEY = os.getenv("OPENAI_API")


def coerce_int_fields(data, fields=("CategoryId", "Sub_categoryId")):
    """Convert string IDs to integers"""
    for item in data.get("skills_acquired", []) or data.get("skills_required", []):
        for f in fields:
            v = item.get(f)
            if isinstance(v, str) and v.isdigit():
                item[f] = int(v)


def fetch_job_details_from_platform(
    job_self_url: str, config: AISkillSearchConfig
) -> dict:
    """Fetch job details directly from JobAdder platform"""
    access_token = config.platform.access_token
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(job_self_url, headers=headers, timeout=30)
        if response.status_code == 401:
            print("Access token expired, refreshing...")
            access_token = config.platform.refresh_access_token()
            if not access_token:
                print("Error: Could not refresh access token")
                return {}

            headers["Authorization"] = f"Bearer {access_token}"
            response = requests.get(job_self_url, headers=headers, timeout=30)

        response.raise_for_status()
        job_data = response.json()

        return {
            "title": job_data.get("title", ""),
            "description": job_data.get("description", ""),
            "summary": job_data.get("summary", ""),
            "location": job_data.get("location", {}).get("city", ""),
            "salary": job_data.get("salary", {}).get("description", ""),
        }
    except Exception as e:
        print(f"Error fetching job details from {job_self_url}: {str(e)}")
        return {}


def extract_skills_from_job_description(job_ad_id: int, job_details: dict) -> list:
    """
    Task 1: Use GPT-4o to extract required skills from job description
    """
    try:
        skills_data = get_skills_collection()
        skills_str = json.dumps(skills_data)

        job_ad_details = json.dumps(job_details, indent=2)

        SCHEMA = return_Schema_require_skills()
        SYSTEM_INSTRUCTIONS, USER_INSTRUCTIONS_TEMPLATE = (
            get_all_instructions_require_skills(job_ad_details, skills_str)
        )

        client = OpenAI(api_key=OPENAI_API_KEY)
        MODEL = "gpt-4o"

        messages = [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": USER_INSTRUCTIONS_TEMPLATE},
        ]

        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.3,
        )

        raw = resp.choices[0].message.content or ""
        content = strip_code_fences(raw)

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            ai_response = find_json_block(content)
            data = json.loads(ai_response)

        coerce_int_fields(data)
        Draft202012Validator(SCHEMA).validate(data)

        ai_response_skills = data.get("skills_required", [])
        print(f"✓ Extracted {len(ai_response_skills)} skills for job {job_ad_id}")

        return ai_response_skills

    except Exception as e:
        print(f"✗ Error extracting skills from job {job_ad_id}: {str(e)}")
        return []


def get_nearby_cities_with_ai(job_location_city: str, radius_km: int) -> list:
    """
    Task 2: Use GPT-4o to get nearby cities within radius
    """
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        MODEL = "gpt-4o"

        SYSTEM_INSTRUCTIONS, USER_INSTRUCTIONS = get_instructions_nearby_cities(
            job_location_city, radius_km
        )

        messages = [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": USER_INSTRUCTIONS},
        ]

        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.3,
        )

        raw = resp.choices[0].message.content or ""
        content = strip_code_fences(raw)

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            ai_response = find_json_block(content)
            data = json.loads(ai_response)

        nearby_cities = data.get("nearby_cities", [])
        if job_location_city not in nearby_cities:
            nearby_cities.insert(0, job_location_city)

        print(f"✓ Found {len(nearby_cities)} nearby cities for {job_location_city}")
        return nearby_cities

    except Exception as e:
        print(f"✗ Error getting nearby cities: {str(e)}")
        return [job_location_city]


def extract_skills_from_employment_history(employment_history: dict) -> list:
    """Extract skills from candidate's employment history using AI"""
    try:
        skills_data = get_skills_collection()
        skills_list = json.dumps(skills_data)

        SCHEMA = return_Schema_acquired_skills()
        SYSTEM_INSTRUCTIONS, USER_INSTRUCTIONS_TEMPLATE = (
            get_all_instructions_compare_employment(employment_history, skills_list)
        )

        client = OpenAI(api_key=OPENAI_API_KEY)
        MODEL = "gpt-4o"

        messages = [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": USER_INSTRUCTIONS_TEMPLATE},
        ]

        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.3,
        )

        raw = resp.choices[0].message.content or ""
        content = strip_code_fences(raw)

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            ai_response = find_json_block(content)
            data = json.loads(ai_response)

        coerce_int_fields(data)
        Draft202012Validator(SCHEMA).validate(data)

        ai_response_skills = data.get("skills_acquired", [])
        return ai_response_skills

    except Exception as e:
        print(f"✗ Error extracting skills from employment history: {str(e)}")
        return []


def fetch_candidates_from_platform(
    nearby_cities: list, config: AISkillSearchConfig, job_ad_id: int
) -> list:
    """
    Fetch candidates directly from JobAdder platform API
    """
    access_token = config.platform.access_token

    if not access_token:
        print("Error: Could not get JobAdder access token")
        return []

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    all_candidates = []

    try:
        # Get candidates URL - you may need to adjust this based on your platform's API
        candidates_url = f"{config.platform.base_url}/candidates"

        response = requests.get(candidates_url, headers=headers, timeout=30)

        if response.status_code == 401:
            print("Access token expired, refreshing...")
            access_token = config.platform.refresh_access_token()
            if not access_token:
                print("Error: Could not refresh access token")
                return []

            headers["Authorization"] = f"Bearer {access_token}"
            response = requests.get(candidates_url, headers=headers, timeout=30)

        response.raise_for_status()
        candidates_data = response.json()

        # Filter candidates by cities and statuses
        for candidate in candidates_data.get("items", []):
            candidate_city = candidate.get("location", {}).get("city", "")
            candidate_status = candidate.get("status", {}).get("name", "")

            # Check if candidate is in nearby cities and has allowed status
            if (
                candidate_city in nearby_cities
                and candidate_status in config.allowed_candidate_statuses
            ):
                # Get full candidate details including skills and employment
                candidate_id = candidate.get("candidateId")
                candidate_details_url = (
                    f"{config.platform.base_url}/candidates/{candidate_id}"
                )

                details_response = requests.get(
                    candidate_details_url, headers=headers, timeout=30
                )

                if details_response.status_code == 200:
                    full_candidate = details_response.json()
                    all_candidates.append(full_candidate)
                    print(f"✓ Fetched candidate {candidate_id} from {candidate_city}")

        print(f"✓ Total candidates fetched: {len(all_candidates)}")
        return all_candidates

    except Exception as e:
        print(f"✗ Error fetching candidates from platform: {str(e)}")
        return []


def match_candidate_skills(
    candidate: dict, required_skills: list, config: AISkillSearchConfig
) -> tuple:
    """
    Task 4: Match candidate skills with required skills
    Returns: (matched: bool, match_source: str, matched_skills: list, match_percentage: float)
    """
    candidate_id = candidate.get("candidateId")
    candidate_skills = candidate.get("skills", [])
    employment_history = candidate.get("employment", {})

    match_source = None
    matched_skills = []

    # Step 1: Check direct skills
    if candidate_skills and len(candidate_skills) > 0:
        print(f"  → Checking direct skills for candidate {candidate_id}")
        matched_skills, match_percentage = calculate_skill_match(
            candidate_skills, required_skills
        )
        if match_percentage >= config.minimum_skill_match_percentage:
            return True, "direct_skills", matched_skills, match_percentage

    # Step 2: Check employment history
    if config.consider_employment_history and employment_history:
        print(f"  → Checking employment history for candidate {candidate_id}")
        employment_skills = extract_skills_from_employment_history(employment_history)

        if employment_skills:
            update_candidate_skills_in_platform(candidate_id, employment_skills, config)
            skills_dict = convert_ai_skills_to_candidate_format(employment_skills)
            matched_skills, match_percentage = calculate_skill_match(
                skills_dict, required_skills
            )
            if match_percentage >= config.minimum_skill_match_percentage:
                return True, "employment_history", matched_skills, match_percentage

    # Step 3: Extract skills from CV
    if config.process_cv_for_skills:
        print(f"  → Processing CV for candidate {candidate_id}")
        cv_skills = extract_skills_from_cv(candidate_id, config)

        if cv_skills:
            update_candidate_skills_in_platform(candidate_id, cv_skills, config)
            skills_dict = convert_ai_skills_to_candidate_format(cv_skills)
            matched_skills, match_percentage = calculate_skill_match(
                skills_dict, required_skills
            )
            if match_percentage >= config.minimum_skill_match_percentage:
                return True, "cv_extraction", matched_skills, match_percentage

    return False, None, [], 0.0


def calculate_skill_match(candidate_skills: list, required_skills: list) -> tuple:
    """Calculate how many required skills match candidate skills"""
    matched_skills = []

    for req_skill in required_skills:
        req_category_id = int(req_skill.get("CategoryId"))
        req_sub_category_id = int(req_skill.get("Sub_categoryId"))

        for cand_skill in candidate_skills:
            cand_category_id = int(cand_skill.get("categoryId"))

            if cand_category_id == req_category_id:
                for sub_cat in cand_skill.get("subCategories", []):
                    cand_sub_id = int(sub_cat.get("subCategoryId"))
                    if cand_sub_id == req_sub_category_id:
                        matched_skills.append(
                            {
                                "CategoryId": req_category_id,
                                "Sub_categoryId": req_sub_category_id,
                            }
                        )
                        break

    match_percentage = (
        (len(matched_skills) / len(required_skills) * 100) if required_skills else 0
    )
    return matched_skills, match_percentage


def convert_ai_skills_to_candidate_format(ai_skills: list) -> list:
    """Convert AI extracted skills to candidate skills format"""
    skills_dict = []
    for skill in ai_skills:
        skill_entry = {
            "categoryId": int(skill.get("CategoryId")),
            "subCategories": [
                {
                    "subCategoryId": int(skill.get("Sub_categoryId")),
                }
            ],
        }
        skills_dict.append(skill_entry)
    return skills_dict


def extract_skills_from_cv(candidate_id: int, config: AISkillSearchConfig) -> list:
    """Extract skills from candidate's CV using platform API"""
    try:
        access_token = config.platform.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Get candidate attachments
        attachments_url = (
            f"{config.platform.base_url}/candidates/{candidate_id}/attachments"
        )
        response = requests.get(attachments_url, headers=headers, timeout=30)

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.get(attachments_url, headers=headers, timeout=30)

        if response.status_code not in [200, 201]:
            print(f"  ✗ No resume found for candidate {candidate_id}")
            return []

        attachments = response.json().get("items", [])
        if not attachments:
            print(f"  ✗ No resume attachments for candidate {candidate_id}")
            return []

        attachment_id = attachments[0].get("attachmentId")

        # Extract skills from CV
        skills_from_cv = cv_skills_extraction(candidate_id, attachment_id)

        if skills_from_cv and skills_from_cv.get("skills"):
            print(f"  ✓ Extracted {len(skills_from_cv['skills'])} skills from CV")
            return skills_from_cv["skills"]

        return []

    except Exception as e:
        print(f"  ✗ Error extracting skills from CV: {str(e)}")
        return []


def update_candidate_skills_in_platform(
    candidate_id: int, skills: list, config: AISkillSearchConfig
):
    """Update candidate skills in JobAdder platform"""
    try:
        access_token = config.platform.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        skills_dict = convert_ai_skills_to_candidate_format(skills)
        skill_update_body = {"skills": skills_dict}

        url = f"{config.platform.base_url}/candidates/{candidate_id}"
        response = requests.put(
            url, json=skill_update_body, headers=headers, timeout=30
        )

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.put(
                    url, json=skill_update_body, headers=headers, timeout=30
                )

        if response.status_code in [200, 201]:
            print(f"  ✓ Updated skills for candidate {candidate_id}")
            return True
        else:
            print(f"  ✗ Failed to update skills for candidate {candidate_id}")
            return False

    except Exception as e:
        print(f"  ✗ Error updating candidate skills: {str(e)}")
        return False


def create_application_for_candidate(
    candidate_id: int, job_ad_id: int, config: AISkillSearchConfig
) -> int:
    """Create application for matched candidate on JobAdder platform"""
    try:
        access_token = config.platform.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Create application
        application_url = f"{config.platform.base_url}/applications"
        application_body = {
            "candidateId": candidate_id,
            "jobAdId": job_ad_id,
            "statusId": config.auto_apply_status_id,
        }

        response = requests.post(
            application_url, json=application_body, headers=headers, timeout=30
        )

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.post(
                    application_url, json=application_body, headers=headers, timeout=30
                )

        if response.status_code in [200, 201]:
            application_data = response.json()
            application_id = application_data.get("applicationId")
            print(
                f"  ✓ Created application {application_id} for candidate {candidate_id}"
            )
            return application_id

        return None

    except Exception as e:
        print(f"  ✗ Error creating application: {str(e)}")
        return None


def send_whatsapp_notification(candidate_id: int, job_ad_id: int, candidate_phone: str):
    """Task 5: Send WhatsApp message to matched candidate"""
    try:
        # Implement WhatsApp notification logic here
        print(f"  ✓ WhatsApp notification sent to candidate {candidate_id}")
        return True
    except Exception as e:
        print(f"  ✗ Error sending WhatsApp: {str(e)}")
        return False


@shared_task
def process_single_job_for_skill_matching(job_ad_id: int, organization_id: int):
    """Process a single job for AI skill matching"""
    try:
        config = AISkillSearchConfig.objects.get(
            organization_id=organization_id, is_active=True
        )
    except AISkillSearchConfig.DoesNotExist:
        print(f"✗ No active AI skill search config for organization {organization_id}")
        return

    # Check if job already processed
    existing_cache = JobSkillCache.objects.filter(job_ad_id=job_ad_id).first()
    if existing_cache:
        print(f"⚠ Job {job_ad_id} already processed")
        return

    print(f"\n{'=' * 60}")
    print(f"Processing Job {job_ad_id} for Organization {organization_id}")
    print(f"{'=' * 60}")

    # Get job details from platform
    try:
        access_token = config.platform.access_token
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        job_url = f"{config.platform.base_url}/jobads/{job_ad_id}"
        response = requests.get(job_url, headers=headers, timeout=30)

        if response.status_code == 401:
            access_token = config.platform.refresh_access_token()
            if access_token:
                headers["Authorization"] = f"Bearer {access_token}"
                response = requests.get(job_url, headers=headers, timeout=30)

        if response.status_code not in [200, 201]:
            print("✗ Failed to fetch job details")
            return

        job_data = response.json()
        job_details = {
            "title": job_data.get("title", ""),
            "description": job_data.get("description", ""),
            "summary": job_data.get("summary", ""),
        }
        location = job_data.get("location", {})
        location_city = location.get("city", "")

    except Exception as e:
        print(f"✗ Error fetching job details: {str(e)}")
        return

    # Task 1: Extract required skills from job description
    print("\n[Task 1] Extracting required skills...")
    required_skills = extract_skills_from_job_description(job_ad_id, job_details)

    if not required_skills:
        print(f"✗ No skills extracted, skipping job {job_ad_id}")
        return

    # Task 2: Get nearby cities
    print(f"\n[Task 2] Finding nearby cities within {config.search_radius_km}km...")
    nearby_cities = get_nearby_cities_with_ai(location_city, config.search_radius_km)

    # Create job skill cache
    job_cache = JobSkillCache.objects.create(
        job_ad_id=job_ad_id,
        organization_id=organization_id,
        job_title=job_details.get("title", ""),
        job_location=f"{location_city}, {location.get('state', '')}",
        job_location_city=location_city,
        required_skills=required_skills,
        nearby_cities=nearby_cities,
        job_description=job_details,
    )

    # Task 3: Fetch candidates from platform
    print("\n[Task 3] Fetching candidates from platform...")
    candidates = fetch_candidates_from_platform(nearby_cities, config, job_ad_id)

    if not candidates:
        print("✗ No candidates found")
        return

    # Task 4: Match candidates
    print("\n[Task 4] Matching candidates with required skills...")
    matched_count = 0

    for idx, candidate in enumerate(candidates[: config.max_candidates_per_job], 1):
        candidate_id = candidate.get("candidateId")
        candidate_name = (
            f"{candidate.get('firstName', '')} {candidate.get('lastName', '')}"
        )

        print(
            f"\n[{idx}/{len(candidates[: config.max_candidates_per_job])}] Candidate {candidate_id} - {candidate_name}"
        )

        # Check if already matched
        existing_match = CandidateSkillMatch.objects.filter(
            candidate_id=candidate_id, job_ad_id=job_ad_id
        ).first()

        if existing_match:
            print("  ⚠ Already matched previously")
            continue

        # Match skills
        is_matched, match_source, matched_skills, match_percentage = (
            match_candidate_skills(candidate, required_skills, config)
        )

        if is_matched:
            matched_count += 1
            print(f"  ✓ MATCH! {match_percentage:.1f}% match via {match_source}")

            application_id = None
            whatsapp_sent = False

            # Auto-apply candidate
            if config.auto_apply_matched_candidates:
                application_id = create_application_for_candidate(
                    candidate_id, job_ad_id, config
                )

            # Send WhatsApp notification
            if config.send_whatsapp_notifications:
                candidate_phone = candidate.get("mobile", "")
                if candidate_phone:
                    whatsapp_sent = send_whatsapp_notification(
                        candidate_id, job_ad_id, candidate_phone
                    )

            # Record match
            CandidateSkillMatch.objects.create(
                candidate_id=candidate_id,
                job_ad_id=job_ad_id,
                organization_id=organization_id,
                matched_skills=matched_skills,
                match_percentage=match_percentage,
                match_source=match_source,
                application_created=application_id is not None,
                application_id=application_id,
                whatsapp_sent=whatsapp_sent,
                whatsapp_sent_at=django_timezone.now() if whatsapp_sent else None,
            )
        else:
            print("  ✗ No match")

    # Update job cache
    job_cache.total_candidates_matched = matched_count
    job_cache.last_matched_at = django_timezone.now()
    job_cache.save()

    print(f"\n{'=' * 60}")
    print(f"✓ Completed: {matched_count} candidates matched for job {job_ad_id}")
    print(f"{'=' * 60}\n")


@shared_task
def scan_and_process_live_jobs_for_all_organizations():
    """
    Main task: Scan all live jobs and process new ones
    """
    print(f"\n{'#' * 80}")
    print("AI Candidate Skill Search - Scanning Live Jobs")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#' * 80}\n")

    # Get all active configs
    active_configs = AISkillSearchConfig.objects.filter(is_active=True)

    if not active_configs.exists():
        print("✗ No active AI skill search configurations found")
        return

    total_processed = 0

    for config in active_configs:
        print(f"\nProcessing organization: {config.organization.name}")

        try:
            access_token = config.platform.access_token
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            # Fetch live jobs from platform
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
            live_jobs = jobs_data.get("items", [])

            print(f"✓ Found {len(live_jobs)} live jobs for {config.organization.name}")

            # Process each job
            for job in live_jobs:
                job_ad_id = job.get("adId")
                job_state = job.get("state")

                # Check if job matches the status for skill search
                if job_state != config.jobad_status_for_skill_search:
                    continue

                # Check if already processed
                if JobSkillCache.objects.filter(
                    job_ad_id=job_ad_id, is_processed=True
                ).exists():
                    continue

                # Process job asynchronously
                process_single_job_for_skill_matching.delay(
                    job_ad_id, config.organization_id
                )
                total_processed += 1
                time.sleep(1)  # Rate limiting

        except Exception as e:
            print(
                f"✗ Error processing organization {config.organization.name}: {str(e)}"
            )
            continue

    print(f"\n✓ Queued {total_processed} jobs for processing")


@shared_task
def initiate_ai_skill_search():
    """
    Periodic task to be run every 3 hours
    """
    scan_and_process_live_jobs_for_all_organizations.delay()
