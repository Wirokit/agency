from typing import Optional

import boto3
import re
import json
from dataclasses import dataclass


@dataclass
class CV_experience:
    title: str
    company_name: str
    time_period: str
    description: str


@dataclass
class CV_education:
    degree: str
    school: str
    time_period: str
    description: str


@dataclass
class CV_data:
    name: str
    title: str
    profile_texts: list[str]
    skills: list[str]
    highlight_skills: list[str]
    job_experience: list[CV_experience]
    education: list[CV_education]

    def toJSON(self):
        return json.dumps(
            {
                "name": self.name,
                "title": self.title,
                "profile_texts": self.profile_texts,
                "skills": self.skills,
                "highlight_skills": self.highlight_skills,
                "job_experience": [
                    vars(experience) for experience in self.job_experience
                ],
                "education": [vars(education) for education in self.education],
            }
        )


def _get_extract_prompt(cv_text, first_name_only):
    return f"""
        Task: Extract the following CV information from the text:
        - "name": The {"first" if first_name_only else "full"} name of the CV owner.
        - "title": The job title of the CV owner.
        - "profile_texts": An array of profile paragraphs.
        - "skills": Array of skills as discrete, one-to-two-word Sentence Case 'tags.' Remove redundant words like 'knowledge of,' 'processes,' or 'experience in.'
        - "job_experience": Array of objects containing a job title (as title), company name (as company_name), time period (as time_period) and description of a listed work experience. Return non-existing values as empty strings.
        - "education": Array of objects containing a degree, school, time period (as time_period) and description of a listed education. Return non-existing values as empty strings.

        CV Text:
        {cv_text}
    """


def _get_highlight_prompt(skills, keyword_list):
    return f"""
        I am going to provide a Job Description and a Master Skill List.

        Your task is to analyze the Job Description and extract only the skills from my Master Skill List that are relevant or implicitly required for the role.

        Return the extracted skill array as "highlight_skills".

        Job Description: ""\"{keyword_list}""\"
        Master Skill List: ""\"{json.dumps(skills)}""\"
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


def extract_cv(cv_data, first_name_only=True):
    prompt = _get_extract_prompt(cv_data, first_name_only)
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
