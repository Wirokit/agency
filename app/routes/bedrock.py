import boto3
import re
import json


def _get_extract_prompt(cv_text, first_name_only):
    return f"""
        Task: Extract the following CV information from the text:
        - "name": The {"first" if first_name_only else "full"} name of the CV owner.
        - "title": The job title of the CV owner.
        - "profileTexts": An array of profile paragraphs.
        - "skills": Array of skills as discrete, one-to-two-word Sentence Case 'tags.' Remove redundant words like 'knowledge of,' 'processes,' or 'experience in.'
        - "workExperience": Array of objects containing a job title (as title), company name (as companyName), time period (as timePeriod) and description of a listed work experience. Return non-existing values as empty strings.
        - "education": Array of objects containing a degree, school, time period (as timePeriod) and description of a listed education. Return non-existing values as empty strings.

        CV Text:
        {cv_text}
    """


def _get_highlight_prompt(skills, keyword_list):
    return f"""
        I am going to provide a Job Description and a Master Skill List.

        Your task is to analyze the Job Description and extract only the skills from my Master Skill List that are relevant or implicitly required for the role.

        Return the extracted skill array as "highlightSkills".

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
    return _query_bedrock_for_json(prompt)


def highlight_skills(skills, job_description):
    prompt = _get_highlight_prompt(skills, job_description)
    return _query_bedrock_for_json(prompt)
