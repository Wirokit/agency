import os
from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from .bedrock import extract_cv
from .utils import parse_pdf


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

    # Remove original file if it exists
    if os.path.exists(original_filepath):
        os.remove(original_filepath)

    return cv_data
