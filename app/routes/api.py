from flask import Blueprint, jsonify, request, session, current_app
from app.db import get_db
from .route_utils import (
    auth_required,
    get_cv_by_pin,
    get_user_record,
    allowed_file,
    parse_pdf,
    generate_pin,
)
import os
import json
from werkzeug.utils import secure_filename
from .bedrock import extract_cv, highlight_skills
import uuid

# Define the Blueprint
api_bp = Blueprint("api", __name__)


@api_bp.route("/cv", methods=["POST"])
@auth_required(modes=["admin"])
def upload_file():
    """
    Handles file upload, processing, and returns a link to the new file.
    """

    # Check if a file was sent
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file part in the request."}), 400

    # Get contact data for the current user
    user_data = get_user_record(session.get("user_id"), "contact_id")

    file = request.files["file"]
    first_name_only = request.values["firstNameOnly"]
    keyword_list = request.values["keywordList"]
    profile_text = request.values["profileText"]

    # Check if the user selected a file
    if file.filename == "":
        return jsonify({"success": False, "error": "No file selected."}), 400

    # Check if the file is an allowed type (PDF)
    if not allowed_file(file.filename):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "File type not allowed. Please upload a PDF.",
                }
            ),
            400,
        )

    # Secure the filename (prevents directory traversal attacks)
    original_filename = secure_filename(file.filename)

    # Save the original file
    original_filepath = os.path.join(
        current_app.config["UPLOAD_FOLDER"], original_filename
    )
    file.save(original_filepath)

    # Parse PDF into raw string
    cv_data = parse_pdf(original_filepath)
    parsed_json = extract_cv(cv_data, first_name_only=first_name_only)

    ### Highlight skills based on keywords, if provided. ###
    if keyword_list != "":
        highlight_json = highlight_skills(parsed_json["skills"], keyword_list)
        parsed_json["highlightSkills"] = highlight_json["highlightSkills"]

        # Remove duplicate skills
        for skill in parsed_json["highlightSkills"]:
            if skill in parsed_json["skills"]:
                parsed_json["skills"].remove(skill)

    # Inject custom profile text into the json object
    if profile_text != "":
        parsed_json["profileTexts"].append(profile_text)

    # Generate a unique ID for the processed CV
    file_id = str(uuid.uuid4())

    db = get_db()  # Get connection from pool
    with db.cursor() as cur:
        # Add new CV to the database
        query = """
            INSERT INTO cv (id, data_owner, date_uploaded, cv_json, contact_id)
            VALUES (%s, %s, now(), %s, %s)
        """
        cur.execute(
            query,
            (
                file_id,
                parsed_json["name"],
                json.dumps(parsed_json),
                user_data["contact_id"],
            ),
        )
        db.commit()

    # Build the URL for the new file
    # This URL points to our '/view/' endpoint below
    new_url = f"/view/{file_id}"

    # Remove original file if it exists
    if os.path.exists(original_filepath):
        os.remove(original_filepath)

    # Send the success response
    return jsonify({"success": True, "url": new_url})


@api_bp.route("/cv", methods=["GET"])
@auth_required(modes=["admin"])
def getCVList():
    """Returns a list of all CVs"""

    db = get_db()
    with db.cursor() as cur:
        query = """
            SELECT id, data_owner, date_uploaded FROM cv
            ORDER BY date_uploaded DESC
        """
        cur.execute(query)
        result = cur.fetchall()

    return jsonify({"success": False, "data": result})


# Used by users that have loggen in via PIN to upload their own CV
# Settings were previously set by admins in create_pin()
@api_bp.route("/cv", methods=["UPDATE"])
@auth_required(modes=["pin_user"])
def update_cv():
    # Ensure that a file was sent
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file part in the request."}), 400

    file = request.files["file"]

    # Secure the original filename (prevents directory traversal attacks)
    original_filename = secure_filename(file.filename)

    # Save the original file
    original_filepath = os.path.join(
        current_app.config["UPLOAD_FOLDER"], original_filename
    )
    file.save(original_filepath)

    db = get_db()
    with db.cursor() as cur:
        # Fetch a db entry based on provided id
        query = """
            SELECT id, settings_json FROM cv
            WHERE pin_code = %s
        """
        cur.execute(query, (session.get("pin_code"),))
        result = cur.fetchone()

    first_name_only = result["settings_json"]["first_name_only"] or False
    keyword_list = result["settings_json"]["keyword_list"] or []
    profile_text = result["settings_json"]["profile_text"] or ""

    # Parse PDF into raw string
    cv_data = parse_pdf(original_filepath)

    parsed_json = extract_cv(cv_data, first_name_only)

    ### Highlight skills based on keywords, if provided. ###
    if keyword_list != "":
        highlight_json = highlight_skills(parsed_json["skills"], keyword_list)
        parsed_json["highlightSkills"] = highlight_json["highlightSkills"]

        # Remove duplicate skills
        for skill in parsed_json["highlightSkills"]:
            if skill in parsed_json["skills"]:
                parsed_json["skills"].remove(skill)

    # Inject custom profile text into the json object
    if profile_text != "":
        parsed_json["profileTexts"].append(profile_text)

    db = get_db()
    with db.cursor() as cur:
        # Add new CV to the database
        query = """
            UPDATE cv
            SET date_uploaded = now(), cv_json = %s
            WHERE pin_code = %s
        """
        cur.execute(
            query,
            (
                json.dumps(parsed_json),
                session.get("pin_code"),
            ),
        )
        db.commit()

    # Remove original file if it exists
    if os.path.exists(original_filepath):
        os.remove(original_filepath)

    # Send the success response
    return jsonify({"success": True})


@api_bp.route("/pin", methods=["POST"])
@auth_required(modes=["admin"])
def create_pin():
    """
    Creates an empty CV entry with a PIN so a CV can be uploaded by them at a later date
    """

    user_data = get_user_record(session.get("user_id"), "contact_id")

    db = get_db()
    with db.cursor() as cur:
        # Iterate to find a unique PIN code to assign
        pin = ""
        failed_attempts = 0
        while True:
            pin = generate_pin()

            # Ensure PIN is unique
            query = "SELECT 1 FROM cv WHERE pin_code = %s"
            cur.execute(query, (pin,))

            row = cur.fetchone()
            if row == None:
                break
            else:
                failed_attempts += 1

            if failed_attempts == 3:
                message = "Generating a unique PIN failed 3 times. This shouldn't happen, so something is likely wrong."
                print(message)
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": message,
                        }
                    ),
                    500,
                )

        # Delete the rows with the provided IDs
        query = "INSERT INTO cv (id, data_owner, pin_code, contact_id, settings_json) VALUES (%s, %s, %s, %s, %s)"
        cur.execute(
            query,
            (
                uuid.uuid4(),
                request.values["recipientIdentifier"],
                pin,
                user_data["contact_id"],
                json.dumps(
                    {
                        "first_name_only": request.values["firstNameOnly"] == "true",
                        "keyword_list": request.values["keywordList"],
                        "profile_text": request.values["profileText"],
                    }
                ),
            ),
        )
        db.commit()

    # Send the success response
    return jsonify({"success": True, "pin": pin})


@api_bp.route("/cv", methods=["DELETE"])
@auth_required(modes=["admin", "pin_user"])
def delete_file():
    """
    Handles file deletion.
    """

    cv_id_list = json.loads(request.values["cvListJson"])

    # If logged in by PIN, ensure the CV being deleted corresponds to the PIN used
    # assumes first CV if somehow multiple were sent
    if "pin_code" in session:
        if len(cv_id_list) > 1:
            return jsonify({"success": False, "error": "Access forbidden."}), 403

        cv_record = get_cv_by_pin(session["pin_code"])
        cv_id = cv_id_list[0]
        if str(cv_record["id"]) != cv_id:
            return jsonify({"success": False, "error": "Access forbidden."}), 403

    db = get_db()
    with db.cursor() as cur:
        # Delete the rows with the provided IDs
        query = "DELETE FROM cv WHERE id IN %s"
        cur.execute(query, (tuple(cv_id_list),))
        db.commit()

    # Send the success response
    return jsonify({"success": True})


@api_bp.route("/cv-edit", methods=["UPDATE"])
@auth_required(modes=["admin"])
def edit_cv():
    """
    Handles json updates when admin edits the cv
    """

    cv_id = request.values["cv_id"]
    cv_json = json.loads(request.values["cv_json"])

    db = get_db()
    with db.cursor() as cur:
        query = """
            UPDATE cv
            SET cv_json = %s
            WHERE id = %s
        """
        cur.execute(
            query,
            (
                json.dumps(cv_json),
                cv_id,
            ),
        )
        db.commit()

    # Send the success response
    return jsonify({"success": True})


@api_bp.route("/privacy-policy", methods=["GET"])
def get_privacy_policy():
    """
    Returns the privacy policy in HTML form.
    """

    privacy_policy = open(current_app.config["PRIVACY_POLICY_PATH"], "r").read()

    return privacy_policy
