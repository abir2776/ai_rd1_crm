# utils.py
import json
import re
from typing import Any, Dict


def strip_code_fences(text: str) -> str:
    """Remove markdown code fences from text"""
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


def find_json_block(text: str) -> str:
    """Find and extract JSON block from text"""
    # Try to find JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)

    # Try to find JSON array
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        return match.group(0)

    return text


def return_Schema_require_skills():
    """JSON schema for required skills extraction"""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "skills_required": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "CategoryId": {"type": "integer"},
                        "Sub_categoryId": {"type": "integer"},
                        "skill_name": {"type": "string"},
                    },
                    "required": ["CategoryId", "Sub_categoryId"],
                },
            }
        },
        "required": ["skills_required"],
    }


def return_Schema_acquired_skills():
    """JSON schema for acquired skills from employment history"""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "skills_acquired": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "CategoryId": {"type": "integer"},
                        "Sub_categoryId": {"type": "integer"},
                        "skill_name": {"type": "string"},
                    },
                    "required": ["CategoryId", "Sub_categoryId"],
                },
            }
        },
        "required": ["skills_acquired"],
    }


def get_all_instructions_require_skills(job_details: str, skills_collection: str):
    """Get AI instructions for extracting required skills from job description"""

    SYSTEM_INSTRUCTIONS = f"""You are an expert HR and recruitment AI assistant specialized in analyzing job descriptions and extracting required skills.

Your task is to analyze the given job description and identify ALL required skills that match the provided skills collection.

The skills collection contains categories, subcategories, and specific skills organized hierarchically:
{skills_collection}

Important guidelines:
1. Extract ALL skills mentioned or implied in the job description
2. Match skills to the exact CategoryId and Sub_categoryId from the skills collection
3. Include both explicitly mentioned skills and implied skills based on job responsibilities
4. Be comprehensive - include technical skills, soft skills, certifications, and qualifications
5. Return ONLY valid IDs that exist in the skills collection
6. If a general category is mentioned (e.g., "Construction experience"), include relevant subcategories

Return your response as a JSON object with this structure:
{{
    "skills_required": [
        {{
            "CategoryId": <integer>,
            "Sub_categoryId": <integer>,
            "skill_name": "<name of the skill>"
        }}
    ]
}}
"""

    USER_INSTRUCTIONS = f"""Analyze this job description and extract all required skills:

{job_details}

Identify every skill requirement and match them to the skills collection provided. Be thorough and comprehensive.
Return ONLY the JSON response with no additional text."""

    return SYSTEM_INSTRUCTIONS, USER_INSTRUCTIONS


def get_all_instructions_compare_employment(
    employment_history: dict, skills_collection: str
):
    """Get AI instructions for extracting skills from employment history"""

    employment_str = json.dumps(employment_history, indent=2)

    SYSTEM_INSTRUCTIONS = f"""You are an expert HR and recruitment AI assistant specialized in analyzing employment history and identifying acquired skills.

Your task is to analyze the given employment history and identify ALL skills the candidate has likely acquired based on their work experience.

The skills collection contains categories, subcategories, and specific skills organized hierarchically:
{skills_collection}

Important guidelines:
1. Analyze job titles, descriptions, and responsibilities
2. Infer skills based on typical requirements for those positions
3. Match skills to exact CategoryId and Sub_categoryId from the skills collection
4. Consider both technical and transferable skills
5. Look for keywords like specific tools, technologies, certifications, or methodologies
6. Return ONLY valid IDs that exist in the skills collection

Return your response as a JSON object with this structure:
{{
    "skills_acquired": [
        {{
            "CategoryId": <integer>,
            "Sub_categoryId": <integer>,
            "skill_name": "<name of the skill>"
        }}
    ]
}}
"""

    USER_INSTRUCTIONS = f"""Analyze this candidate's employment history and extract all skills they have acquired:

{employment_str}

Identify skills from job titles, descriptions, and work experience. Be thorough and consider both explicit and implicit skills.
Return ONLY the JSON response with no additional text."""

    return SYSTEM_INSTRUCTIONS, USER_INSTRUCTIONS


def get_instructions_nearby_cities(location_city: str, radius_km: int):
    """Get AI instructions for finding nearby cities within radius"""

    SYSTEM_INSTRUCTIONS = """You are a geography expert AI assistant specialized in identifying nearby cities and locations.

Your task is to provide a list of cities, towns, and areas within a specified radius of a given location.

Important guidelines:
1. Include the original city in the list
2. List all significant cities, towns, and neighborhoods within the radius
3. Be comprehensive - include suburbs, districts, and nearby areas
4. Consider the geography and urban layout of the region
5. Prioritize populated areas where candidates are likely to live
6. For UK locations, include relevant boroughs, districts, and postal areas

Return your response as a JSON object with this structure:
{
    "nearby_cities": ["City1", "City2", "City3", ...]
}
"""

    USER_INSTRUCTIONS = f"""Find all cities, towns, and areas within {radius_km} kilometers of {location_city}.

Include the main city, suburbs, neighborhoods, and any nearby populated areas where job candidates might live.

For context:
- Location: {location_city}
- Radius: {radius_km} km

Return a comprehensive list as a JSON array. Return ONLY the JSON response with no additional text."""

    return SYSTEM_INSTRUCTIONS, USER_INSTRUCTIONS


def format_skills_for_display(skills: list, skills_collection: dict) -> list:
    """Format skills with human-readable names from collection"""
    formatted = []

    skills_dict = skills_collection.get("skills", [])

    for skill in skills:
        cat_id = skill.get("CategoryId")
        sub_cat_id = skill.get("Sub_categoryId")

        # Find category and subcategory names
        cat_name = "Unknown Category"
        sub_cat_name = "Unknown Subcategory"

        for category in skills_dict:
            if category.get("categoryId") == cat_id:
                cat_name = category.get("name", "Unknown")

                for sub_cat in category.get("subCategories", []):
                    if sub_cat.get("subCategoryId") == sub_cat_id:
                        sub_cat_name = sub_cat.get("name", "Unknown")
                        break
                break

        formatted.append(
            {
                "CategoryId": cat_id,
                "Sub_categoryId": sub_cat_id,
                "category_name": cat_name,
                "subcategory_name": sub_cat_name,
            }
        )

    return formatted


def calculate_match_score(
    matched_skills: list, required_skills: list, candidate_skills: list
) -> dict:
    """Calculate detailed match score metrics"""

    total_required = len(required_skills)
    total_matched = len(matched_skills)
    total_candidate = len(candidate_skills)

    match_percentage = (
        (total_matched / total_required * 100) if total_required > 0 else 0
    )
    skill_coverage = (
        (total_matched / total_candidate * 100) if total_candidate > 0 else 0
    )

    return {
        "total_required_skills": total_required,
        "total_matched_skills": total_matched,
        "total_candidate_skills": total_candidate,
        "match_percentage": round(match_percentage, 2),
        "skill_coverage": round(skill_coverage, 2),
        "is_strong_match": match_percentage >= 75,
        "is_good_match": 50 <= match_percentage < 75,
        "is_partial_match": 25 <= match_percentage < 50,
    }


def generate_match_summary(
    candidate: dict, job_title: str, matched_skills: list, match_percentage: float
) -> str:
    """Generate human-readable match summary"""

    candidate_name = f"{candidate.get('firstName', '')} {candidate.get('lastName', '')}"

    summary = f"""
Candidate Match Summary
{"=" * 50}
Candidate: {candidate_name} (ID: {candidate.get("candidateId")})
Job: {job_title}
Match Score: {match_percentage:.1f}%
Matched Skills: {len(matched_skills)}

Match Rating: {get_match_rating(match_percentage)}

This candidate has been automatically identified as a potential match
based on their skills and experience profile.
"""

    return summary


def get_match_rating(match_percentage: float) -> str:
    """Get match rating label"""
    if match_percentage >= 90:
        return "⭐⭐⭐⭐⭐ Excellent Match"
    elif match_percentage >= 75:
        return "⭐⭐⭐⭐ Very Good Match"
    elif match_percentage >= 60:
        return "⭐⭐⭐ Good Match"
    elif match_percentage >= 50:
        return "⭐⭐ Fair Match"
    else:
        return "⭐ Partial Match"


def validate_config(config: dict) -> tuple:
    """Validate AI skill search configuration"""
    errors = []

    if config.get("search_radius_km", 0) < 1:
        errors.append("Search radius must be at least 1 km")

    if config.get("search_radius_km", 0) > 500:
        errors.append("Search radius cannot exceed 500 km")

    if not isinstance(config.get("candidate_status_ids"), list):
        errors.append("Candidate status IDs must be a list")

    if config.get("minimum_skill_match_percentage", 0) < 0:
        errors.append("Minimum match percentage cannot be negative")

    if config.get("minimum_skill_match_percentage", 0) > 100:
        errors.append("Minimum match percentage cannot exceed 100")

    if config.get("max_candidates_per_job", 0) < 1:
        errors.append("Max candidates per job must be at least 1")

    is_valid = len(errors) == 0
    return is_valid, errors


def return_Schema_cv_skills():
    SCHEMA: Dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "skills": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "Category": {"type": "string"},
                        "CategoryId": {"type": "integer"},
                        "Sub_category": {
                            "type": "string"
                        },  # e.g., Construction, Logistics
                        "Sub_categoryId": {"type": "integer"},
                    },
                    "required": [
                        "Category",
                        "CategoryId",
                        "Sub_category",
                        "Sub_categoryId",
                    ],
                },
            }
        },
        "required": ["skills"],
    }
    return SCHEMA


def get_all_instructions_cv_skills(cv_text: str, skills_list: str):
    SYSTEM_INSTRUCTIONS = (
        "You are a skilled CV parser. Your task is to extract career related skills from the CV text against the predefined skills list.\n"
        "Task: From the given CV/resume text, list every skills set the candidate has (past and present) by matching them with the predefined skills list.\n"
        "Carefully read the cv text and try to deeply understand what are the skills of this person has. Because it's not a skill if the person just mention the word into their cv. You have to see they have experience, passions, intention to work on that topic. You have to see they have worked before on that topic, or is wanting to make career on this topic.\n"
        "And furthermore the CV owner must have expertise on the skill topic. Anyone can say I have worked in Microsoft excel or word, but that doesn't mean they have IT skills. You are not listing the skills the person has, instead you are listing the skills the person is choosing for career."
        "- Create multiple items of the same category which has different sub-categories.\n"
        "- Only find skills explicitly present in the CV text, and in the predefined skills list; do NOT invent new skills\n"
        "- Both category and sub-category must be filled in for each skill item. If both are not present, the item should be excluded from the results.\n"
        '- If no skills are found, return an empty skills array: {"skills": []}\n'
        "- Return ONLY raw JSON (no markdown fences, no extra prose) with this structure:\n"
        "{\n"
        '  "skills": [\n'
        "    {\n"
        '      "Category": "",\n'
        '      "CategoryId": "",\n'
        '      "Sub_category": "",\n'
        '      "Sub_categoryId": "",\n'
        '      "Return ONLY raw JSON matching the specified structure (no markdown, no extra text).\n\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "- Here is the predefined skills set you must use to match against the CV text:\n"
        "PREDEFINED SKILLS set START\n"
        f"{skills_list}\n"
        "SKILLS LIST set END\n"
    )

    USER_INSTRUCTIONS_TEMPLATE = (
        "Find the skills in the CV text by matching them with the predefined skills list.\n"
        "Some skills may be context-specific or require inference based on the CV content.\n"
        "Return ONLY raw JSON matching the specified structure (no markdown, no extra text).\n\n"
        "CV TEXT START\n"
        f"{cv_text}\n"
        "CV TEXT END\n"
    )

    return SYSTEM_INSTRUCTIONS, USER_INSTRUCTIONS_TEMPLATE
