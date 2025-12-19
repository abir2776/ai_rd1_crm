"""
Goal: set skills for candidates based on their last uploaded CV/resume in the database system.

Step 1: get CV text from process_cv.py + Skills set from skills.json
Step 2: create instructions for skills extraction, feed the Skills json data to LLM model
Step 3: return skills json data
"""

import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
import json

import requests
from jsonschema import Draft202012Validator

from .collection_skills import get_skills_collection
from .process_cv import process_cv
from .utils import (
    find_json_block,
    get_all_instructions_cv_skills,
    return_Schema_cv_skills,
    strip_code_fences,
)

#### Testing Starts Here ####


def cv_skills_extraction(candidate_id: int, attachmentId: int, base_url: str):
    print("****************** Here starts CV processing *****************")

    # Ensure CV folder exists
    download_dir = "skill_module_cvs"
    os.makedirs(download_dir, exist_ok=True)

    # CV file path
    cv_file_path = os.path.join(
        download_dir, f"candidate_{candidate_id}_attachment_{attachmentId}.pdf"
    )

    # Download CV using base_url
    download_url = f"{base_url}/candidates/{candidate_id}/attachments/{attachmentId}"

    download_resume = requests.get(download_url, timeout=60)

    if download_resume.status_code not in (200, 201):
        print(
            f"Failed to download resume for Candidate ID {candidate_id}. "
            f"Status code: {download_resume.status_code}"
        )
        return None

    response_json = download_resume.json()
    if not response_json.get("success"):
        print("CV download failed:", response_json)
        return None

    # Step 1: process CV
    cleaned_cv_text = process_cv(cv_file_path)

    # Clean up downloaded CV
    try:
        os.remove(cv_file_path)
    except FileNotFoundError:
        pass

    skills_data = get_skills_collection()
    skills_list = json.dumps(skills_data)

    print("** Step 1: finished")

    # Step 2: prepare LLM instructions
    SCHEMA = return_Schema_cv_skills()
    SYSTEM_INSTRUCTIONS, USER_INSTRUCTIONS_TEMPLATE = get_all_instructions_cv_skills(
        cleaned_cv_text, skills_list
    )

    print("** Step 2: finished")

    # Step 3: call OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API"))
    MODEL = "gpt-5-mini-2025-08-07"

    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTIONS},
        {"role": "user", "content": USER_INSTRUCTIONS_TEMPLATE},
    ]

    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        # DO NOT send temperature/top_p/etc. for this model
    )

    raw = resp.choices[0].message.content or ""
    content = strip_code_fences(raw)

    # Parse JSON safely
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        ai_response = find_json_block(content)
        data = json.loads(ai_response)

    # Validate schema
    try:
        Draft202012Validator(SCHEMA).validate(data)
        print("Final Validated Output JSON:")
        return data
    except Exception as e:
        print("Validation Error:", str(e))
        print("Raw content was:")
        print(raw)

    return None
