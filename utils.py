import random
import math
import fitz
import boto3
import re
import json


def generate_pin():
    """
    Generates a random 6-digit pin code
    """

    digits = [i for i in range(0, 10)]

    random_str = ""

    for i in range(6):
        index = math.floor(random.random() * 10)
        random_str += str(digits[index])

    ## displaying the random string
    return random_str


def parse_pdf(file):
    """Reads a PDF file from the local server and extracts all text."""
    try:
        doc = fitz.open(file)
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return None


def generate_extraction_prompt(
    cv_data,
    first_name_only=False,
):
    return f"""
        Task: Extract the following details from the text:
        - "name": The {"first" if first_name_only else ""} name of the CV owner.
        - "title": The job title of the CV owner.
        - "profileTexts": An array of profile paragraphs.
        - "skills": Array of skills as discrete, one-to-two-word Sentence Case 'tags.' Remove redundant words like 'knowledge of,' 'processes,' or 'experience in.'
        - "workExperience": Array of objects containing a job title (as title), company name (as companyName), time period (as timePeriod) and description of a listed work experience.
        - "education": Array of objects containing a degree, school, time period (as timePeriod) and description of a listed education.

        CV Text:
        {cv_data}
    """


def query_bedrock(prompt):
    # Initialize the Bedrock client
    # boto3 automatically picks up AWS credentials from the environment
    bedrock = boto3.client("bedrock-runtime", region_name="eu-central-1")

    # Using the Cross-Region Inference profile for Europe
    model_id = "eu.anthropic.claude-3-haiku-20240307-v1:0"

    try:
        response = bedrock.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            system=[
                {
                    "text": "You are a precise data extraction bot. Your ONLY job is to output valid JSON. No markdown formatting, no conversational filler, and no introductory text. Start directly with '{'."
                }
            ],
            inferenceConfig={
                "temperature": 0.1,  # Low temperature for highly factual extraction
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
    except Exception as e:
        print(f"Bedrock API Error: {e}")
        return None


# --- Testing functions ---

if __name__ == "__main__":
    print(f"Generated pin: {generate_pin()}")
