import boto3
import re
import json

from models import CV_data, Skill


def _get_extract_prompt(cv_text):
    return f"""
        Task: Extract the following CV information from the text:
        - "name": The full name of the CV owner.
        - "title": The job title of the CV owner.
        - "profile_texts": An array of profile paragraphs.
        - "skills": Array of objects containing a skill name (as name) and a proficiency value as a number between 1 and 5 (as proficiency). The skill names should be discrete, one-to-two-word Sentence Case 'tags.' Remove redundant words like 'knowledge of,' 'processes,' or 'experience in.' The proficiency should be 1 if indicated skill experience is less than a year, 2 means 1-3 years, 3 means 4-5 years, 4 means 6-7 years and 5 means 8+ years of experience.
        - "job_experience": Set as an empty array if no job experience is defined. Otherwise, set as an array of objects containing the following
            - title (String): Extract the formal job title only. Strip out department names, team names, or geographic locations if they are attached to the title in the CV (e.g., extract "Software Engineer", not "Software Engineer - Frontend Team"). If a title is missing, output null.
            - company_name (String): Extract the legal or trading name of the company. Strip out business entity suffixes (LLC, Inc., Ltd.) and location data (e.g., extract "Acme Corp", not "Acme Corp Ltd, London").
            - description (String): Extract the responsibilities and achievements. If the CV uses bullet points, format the output using Markdown bullet points (- ). Remove any UI artifacts, page numbers, or irrelevant symbols (e.g., ***, |, Page 2) caught in the parse. Do not summarize or shorten the text; preserve the original phrasing. Leave empty if not found.
            - start_date & end_date (String, ISO 8601): Must be in YYYY-MM-DD format. If the CV only provides a year (e.g., "2021"), default the month and day to January 1st (e.g., "2021-01-01"). If there is only one date, set it to end_date and leave start_date empty. If the job is current (e.g., "Present", "Current", "To Date"), leave end_date empty.
            - start_display_month & end_display_month (Boolean): Controls UI rendering. Set to true ONLY IF the raw CV text explicitly includes a month, season, or exact date (e.g., "March 2021", "Q2 2021", "Fall 2021"). Set to false IF the raw CV text provides ONLY a year (e.g., "2021", "2018 - 2020").
        - "education": Set as an empty array if no education is defined. Otherwise, set as an array of objects containing the following
            - degree (String): The studied degree or course.
            - school (String): The name of the school or other facility.
            - description (String): Description for the study. Leave empty if not found.
            - start_date & end_date (String, ISO 8601): Must be in YYYY-MM-DD format. If the CV only provides a year (e.g., "2021"), default the month and day to January 1st (e.g., "2021-01-01"). If there is only one date, set it to end_date and leave start_date empty. If the education is current (e.g., "Present", "Current", "To Date"), leave end_date empty.
            - start_display_month & end_display_month (Boolean): Controls UI rendering. Set to true ONLY IF the raw CV text explicitly includes a month, season, or exact date (e.g., "March 2021", "Q2 2021", "Fall 2021"). Set to false IF the raw CV text provides ONLY a year (e.g., "2021", "2018 - 2020").

        CV Text:
        {cv_text}
    """


def _get_highlight_prompt(skills, job_description):
    return f"""
        I am going to provide a Job Description and a Master Skill List.

        Your task is to analyze the Job Description and extract only the skills from my Master Skill List that are relevant or implicitly required for the role.

        Return the extracted skill array as "highlight_skills".

        Job Description: ""\"{job_description}""\"
        Master Skill List: ""\"{json.dumps(skills)}""\"
    """


def _get_translation_prompt(language: str, json_str: str):
    return f"""
        I am going to provide a JSON object containing the following CV information:
        - "title": A job title or profession.
        - "profile_texts": An array of profile paragraphs.
        - "job_experience": Array of objects containing a job title (as title), company name (as company_name) and description of a listed work experience.
        - "education": Array of objects containing a degree, school, and description of a listed education.
        - "skills": An array of objects containing a skill name (as name), proficiency level (as proficiency) and a boolean to highlight the skill (as is_highlight).

        Your task is to translate them to {language}. Do not translate technical terms such as "frontend" and "backend", and make necessary changes to keep the translations appropriate for a CV.

        Return the translated values in an identical JSON object.

        JSON object: ""\"{json_str}""\"
    """


def _query_bedrock_for_json(prompt):
    # Initialize the Bedrock client
    # boto3 automatically picks up AWS credentials from the environment
    bedrock = boto3.client("bedrock-runtime", region_name="eu-central-1")

    # Using the Cross-Region Inference profile for Europe
    model_id = "eu.anthropic.claude-3-haiku-20240307-v1:0"

    response = bedrock.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        system=[
            {
                "text": "You are a precise data extraction bot. Your ONLY job is to output valid JSON. No markdown formatting, no conversational filler, and no introductory text. Start directly with '{'."
            }
        ],
        inferenceConfig={
            "temperature": 0,  # Low temperature for highly factual extraction
            "maxTokens": 4096,  # Plenty of room for large JSON outputs
        },
    )

    # Extract the raw text from the Bedrock response
    output_text = response["output"]["message"]["content"][0]["text"]

    # Safety net: Extract only the JSON portion just in case the model adds filler
    json_match = re.search(r"\{.*\}", output_text, re.DOTALL)

    if json_match:
        try:
            parsed_json = json.loads(json_match.group(0))
            return parsed_json
        except json.JSONDecodeError:
            print("Failed to parse the Bedrock output into valid JSON. Raw output:")
            print(output_text)
            return None
    else:
        print("No JSON object found in the response. Raw output:")
        print(output_text)
        return None


def extract_cv(cv_data):
    prompt = _get_extract_prompt(cv_data)
    json = _query_bedrock_for_json(prompt)

    # Fix skills before class conversion
    for skill in json["skills"]:
        skill["is_highlight"] = False

    # Fix issue with empty experience objects before conversion
    # Should only occur in cases where job experience is missing or unreadable
    for exp in json["job_experience"]:
        if exp["title"] is None:
            json["job_experience"].remove(exp)

    return CV_data(**json)


def highlight_skills(skills: list[Skill], job_description: str):
    raw_skills = [skill.name for skill in skills]

    prompt = _get_highlight_prompt(raw_skills, job_description)
    highlight_skills = _query_bedrock_for_json(prompt)["highlight_skills"]

    for skill in skills:
        if skill.name in highlight_skills:
            skill.is_highlight = True

    return skills


def translate_cv(language: str, cv_data: CV_data):
    json_obj = {
        "title": cv_data.title,
        "profile_texts": cv_data.profile_texts,
        "job_experience": [vars(experience) for experience in cv_data.job_experience],
        "education": [vars(education) for education in cv_data.education],
        "skills": [vars(skill) for skill in cv_data.skills],
    }

    prompt = _get_translation_prompt(language, json.dumps(json_obj, ensure_ascii=False))
    return _query_bedrock_for_json(prompt)
