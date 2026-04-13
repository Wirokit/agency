import json
import os
from typing import Optional
from uuid import uuid4, UUID
from flask import current_app
from dataclasses import dataclass
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .bedrock import CV_data, extract_cv, highlight_skills
from .utils import parse_pdf


@dataclass
class CV_settings:
    first_name_only: bool
    job_description: str
    extra_profile_text: str

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__)


@dataclass
class CV:
    id: UUID
    data_owner: str
    settings: CV_settings
    cv_data: Optional[CV_data] = None
    pin_code: Optional[str] = None


def upload_cv(
    file: FileStorage,
    settings: CV_settings,
):
    """
    Handles file upload, processes it into a CV and returns it.
    """

    # Secure the filename (prevents directory traversal attacks)
    original_filename = secure_filename(file.filename)

    # Save the original file
    original_filepath = os.path.join(
        current_app.config["UPLOAD_FOLDER"], original_filename
    )
    file.save(original_filepath)

    # Parse PDF into raw string
    pdf_data = parse_pdf(original_filepath)
    cv_data = extract_cv(pdf_data, first_name_only=settings.first_name_only)

    ### Highlight skills based on job description, if provided. ###
    if settings.job_description != "":
        highlight_json = highlight_skills(cv_data.skills, settings.job_description)
        cv_data.highlight_skills = highlight_json["highlight_skills"]

        # Remove duplicate skills
        for skill in cv_data.highlight_skills:
            if skill in cv_data.skills:
                cv_data.skills.remove(skill)

    # Inject custom profile text into the json object
    if settings.extra_profile_text != "":
        cv_data.profile_texts.append(settings.extra_profile_text)

    # Generate a unique ID for the processed CV
    cv_id = uuid4()

    # Remove original file if it exists
    if os.path.exists(original_filepath):
        os.remove(original_filepath)

    return CV(id=cv_id, data_owner=cv_data.name, settings=settings, cv_data=cv_data)
