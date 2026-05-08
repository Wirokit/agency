import json
import os
from typing import Optional
from uuid import uuid4, UUID
from flask import current_app
from dataclasses import dataclass
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .bedrock import CV_data, extract_cv
from .utils import parse_pdf


@dataclass
class CV_settings:
    language: str
    job_description: str
    extra_profile_text: str

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__)


@dataclass
class CV:
    id: UUID
    data_owner: str
    cv_data: Optional[CV_data] = None


def extract_data_from_cv(
    file: FileStorage,
):
    """
    Reads a PDF file, processes it into a CV object and returns it.
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
    cv_data = extract_cv(pdf_data)

    # Generate a unique ID for the processed CV
    cv_id = uuid4()

    # Remove original file if it exists
    if os.path.exists(original_filepath):
        os.remove(original_filepath)

    return CV(id=cv_id, data_owner=cv_data.name, cv_data=cv_data)
