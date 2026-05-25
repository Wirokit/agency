import boto3
import re
import json

from app.types.cv import CV_data, CV_experience, CV_education


def _get_extract_prompt(cv_text):
    return f"""
        Task: Extract the following CV information from the text:
        - "name": The full name of the CV owner.
        - "title": The job title of the CV owner.
        - "profile_texts": An array of profile paragraphs.
        - "skills": Array of skills as discrete, one-to-two-word Sentence Case 'tags.' Remove redundant words like 'knowledge of,' 'processes,' or 'experience in.'
        - "job_experience": Array of objects containing a job title (as title), company name (as company_name), time period (as time_period) and description of a listed work experience. Return non-existing values as empty strings.
        - "education": Array of objects containing a degree, school, time period (as time_period) and description of a listed education. Return non-existing values as empty strings.

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
        I am going to provide a JSON object containing the following:
        - "profile_texts": An array of profile paragraphs.
        - "job_experience": Array of objects containing a job title (as title), company name (as company_name), time period (as time_period) and description of a listed work experience.
        - "education": Array of objects containing a degree, school, time period (as time_period) and description of a listed education.

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

    return CV_data(
        name=json["name"],
        title=json["title"],
        profile_texts=json["profile_texts"],
        skills=json["skills"],
        highlight_skills=[],
        job_experience=[
            CV_experience(
                title=experience["title"],
                company_name=experience["company_name"],
                time_period=experience["time_period"],
                description=experience["description"],
            )
            for experience in json["job_experience"]
        ],
        education=[
            CV_education(
                degree=education["degree"],
                school=education["school"],
                time_period=education["time_period"],
                description=education["description"],
            )
            for education in json["education"]
        ],
    )


def highlight_skills(skills, job_description):
    prompt = _get_highlight_prompt(skills, job_description)
    return _query_bedrock_for_json(prompt)


def translate_cv(language: str, cv_data: CV_data):
    json_obj = {
        "profile_texts": cv_data.profile_texts,
        "job_experience": [vars(experience) for experience in cv_data.job_experience],
        "education": [vars(education) for education in cv_data.education],
    }

    prompt = _get_translation_prompt(language, json.dumps(json_obj, ensure_ascii=False))
    return _query_bedrock_for_json(prompt)
