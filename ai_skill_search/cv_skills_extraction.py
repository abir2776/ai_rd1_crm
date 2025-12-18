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


def cv_skills_extraction(candidate_id: int, attachmentId: int):
    print("****************** Here starts CV processing *****************")
    cv_file_path = f"candidate_{candidate_id}_attachment_{attachmentId}.pdf"
    download_resume = requests.get(
        f"https://chatbot.rd1.co.uk/document_download_skill_cv?candidateID={candidate_id}&attachmentId={attachmentId}&cv_pdf_file_name={cv_file_path}"
    )
    if download_resume.status_code == 200 or download_resume.status_code == 201:
        if not download_resume.json()["success"]:
            return None
        # Step 1: get CV text from process_cv.py + Skills set from skills.json
        cleaned_cv_text = process_cv(f"skill_module_cvs/{cv_file_path}")
        os.remove(
            f"skill_module_cvs/{cv_file_path}"
        )  # Clean up the downloaded CV file after processing
    else:
        print(
            f"Failed to download resume for Candidate ID {candidate_id}. Status code: {download_resume.status_code}"
        )
        return None

    skills_data = get_skills_collection()
    skills_list = json.dumps(skills_data)

    print("** Step 1: finished")

    # Step 2: create instructions for skills extraction, feed the Skills json data to LLM model
    SCHEMA = return_Schema_cv_skills()
    SYSTEM_INSTRUCTIONS, USER_INSTRUCTIONS_TEMPLATE = get_all_instructions_cv_skills(
        cleaned_cv_text, skills_list
    )
    print("** Step 2: finished")

    # Step 3: return skills json data
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
    raw = resp.choices[0].message.content or ""  # generated response

    content = strip_code_fences(raw)

    # First attempt: direct JSON parse
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        # Recovery: try to locate a JSON object/array in the content
        ai_response = find_json_block(content)
        data = json.loads(ai_response)
    try:
        # Validate against schema (strict)
        Draft202012Validator(SCHEMA).validate(data)

        print("Final Validated Output JSON:")
        # print(data)
        # print(type(data))
        # print("** Step 2: finished")
        return data
    except Exception as e:
        print("Validation Error:", e.message)
        print("Raw content was:")
        print(raw)
    return None
