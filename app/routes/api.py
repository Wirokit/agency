import json
from flask import Blueprint, jsonify, request, session, current_app
from app.db import get_db
from app.services.bedrock import (
    highlight_skills,
    translate_cv,
)
from app.services.s3 import S3_PROFILE_IMG_BUCKET, get_s3_client
from models import CV_data, Education, JobExperience, UserType
from .route_utils import auth_required, get_user_by_id
from app.services.cv import (
    extract_data_from_cv,
    get_source_cv,
    replace_cv_data,
    save_cv_to_db,
)
from app.services.utils import (
    generate_pin,
)
import uuid
import secrets
import string
from app.services.utils import (
    bcrypt,
)

# Set of characters for generating random passwords
alphabet = string.ascii_letters + string.digits

# Define the Blueprint
api_bp = Blueprint("api", __name__)


@api_bp.route("/privacy-policy", methods=["GET"])
def get_privacy_policy():
    """
    Returns the privacy policy in HTML form.
    """

    privacy_policy = open(current_app.config["PRIVACY_POLICY_PATH"], "r").read()

    return privacy_policy


@api_bp.route("/user", methods=["POST"])
@auth_required(modes=["admin"])
def createUser():
    """Create a new user"""

    file = None
    if request.files:
        file = request.files["file"]

    is_admin = request.values["is_admin"] == "true"
    username = request.values["username"]
    full_name = request.values["full_name"]
    location = request.values["location"]
    email = request.values["email"]
    phone = request.values["phone"]

    cv_data = None
    if file and file.filename != "":
        cv_data = extract_data_from_cv(file)

    user_uuid = uuid.uuid4()
    password = "".join(secrets.choice(alphabet) for i in range(20))
    hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

    db = get_db()
    with db.cursor() as cur:
        # Insert the new user into the DB
        query = """
            INSERT INTO users (
                id,
                username,
                full_name,
                title,
                office,
                email,
                phone_num,
                user_type_id,
                password_hash
            ) VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            );
        """
        cur.execute(
            query,
            (
                user_uuid,
                username,
                full_name,
                "" if cv_data is None else cv_data.title,
                location,
                email,
                phone,
                1 if is_admin else 2,
                hashed_password,
            ),
        )
        db.commit()

    if cv_data:
        save_cv_to_db(
            cv=cv_data, user_uuid=user_uuid, user_name=full_name, is_source=True
        )

    return jsonify({"success": True, "user_uuid": user_uuid, "password": password})


@api_bp.route("/external", methods=["POST"])
@auth_required(modes=["admin"])
def createTempUser():
    """Create a temporary user as an external talent"""

    file = request.files["file"]
    full_name = request.values["full_name"]
    email = request.values["email"]
    location = request.values["location"]

    cv_data = None
    if file.filename != "":
        cv_data = extract_data_from_cv(file)

    user_uuid = uuid.uuid4()

    db = get_db()
    with db.cursor() as cur:
        # Iterate to find a unique PIN code to assign
        pin = ""
        failed_attempts = 0
        while True:
            pin = generate_pin()

            # Ensure PIN is unique
            query = "SELECT 1 FROM users WHERE pin_code = %s"
            cur.execute(query, (pin,))

            row = cur.fetchone()
            if row is None:
                break
            else:
                failed_attempts += 1

            if failed_attempts == 3:
                db.rollback()
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

        db.rollback()

        # Insert the new temp user into the DB
        query = """
            INSERT INTO users (
                id,
                full_name,
                email,
                office,
                pin_code,
                user_type_id,
                title
            ) VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                3,
                %s
            );
        """
        cur.execute(
            query,
            (
                user_uuid,
                full_name,
                email,
                location,
                pin,
                "" if cv_data is None else cv_data.title,
            ),
        )
        db.commit()

    if cv_data:
        save_cv_to_db(
            cv=cv_data, user_uuid=user_uuid, user_name=full_name, is_source=True
        )

    return jsonify({"success": True, "pin": pin, "user_uuid": user_uuid})


@api_bp.route("/source-cv/<id>", methods=["PUT"])
@auth_required(modes=["all"])
def upload_source_cv(id):
    # Ensure that a file was sent
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file part in the request."}), 400

    # Ensure that either the user is an admin, or the profile being edited belongs
    # to the logged in user
    if (
        UserType(session["user_type"]) != UserType.ADMIN
        and str(session["user_id"]) != id
    ):
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    # Delete existing source CV from the DB
    db = get_db()
    with db.cursor() as cur:
        query = """
            DELETE FROM cv
            WHERE owner_id = %s and is_source = True;
        """
        cur.execute(
            query,
            (id,),
        )
        # Commit will be done in save_to_db if successful

    cv_data = extract_data_from_cv(request.files["file"])
    save_cv_to_db(
        cv=cv_data, user_uuid=id, user_name=session["user_name"], is_source=True
    )

    # Send the success response
    return jsonify({"success": True})


@api_bp.route("/profile/<id>", methods=["DELETE"])
@auth_required(modes=["admin", "external"])
def delete_user_profile_by_id(id):
    """Used by external users to delete their own profile"""
    """Used by admins to delete any profile"""

    if UserType(session["user_type"]) is UserType.EXTERNAL and id != str(
        session["user_id"]
    ):
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    db = get_db()
    with db.cursor() as cur:
        query = """
            DELETE FROM users
            WHERE id = %s
        """
        cur.execute(query, (id,))

    db.commit()

    return jsonify({"success": True})


@api_bp.route("/profile/<id>", methods=["PATCH"])
@auth_required(modes=["all"])
def edit_profile(id):
    if "profile_image" in request.files:
        file = request.files["profile_image"]

        if file:
            file_name = f"profile-img/{id}.png"
            s3_client = get_s3_client()

            try:
                s3_client.upload_fileobj(
                    file,
                    S3_PROFILE_IMG_BUCKET,
                    file_name,
                    ExtraArgs={"ContentType": file.content_type},
                )

            except Exception as e:
                return jsonify({"error": str(e)}), 500

    full_name = request.values["full_name"]
    title = request.values["title"]
    location = request.values["location"]

    db = get_db()
    with db.cursor() as cur:
        query = """
            UPDATE users
            SET full_name = %s, title = %s, office = %s
            WHERE id = %s
        """

        cur.execute(
            query,
            (
                full_name,
                title,
                location,
                id,
            ),
        )

    db.commit()

    # Send the success response
    return jsonify({"success": True})


@api_bp.route("/targeted-cv/<source_user_id>", methods=["POST"])
@auth_required(modes=["admin"])
def post_targeted_cv(source_user_id):
    source_user_data = get_user_by_id(source_user_id, "full_name, title")

    cv_data = get_source_cv(source_user_id)
    if not cv_data:
        return jsonify({"success": False, "error": "No source CV exists"}), 424

    cv_data.name = source_user_data["full_name"]
    cv_data.title = source_user_data["title"]

    job_name = request.values["job_id"]
    language = request.values["language"]
    job_description = request.values["job_description"]
    extra_profile_text = request.values["extra_profile_text"]
    contact_user_id = request.values["contact"]

    if language:
        translated_json = translate_cv(language, cv_data)
        cv_data.profile_texts = translated_json["profile_texts"]
        cv_data.job_experience = [
            JobExperience(**experience)
            for experience in translated_json["job_experience"]
        ]
        cv_data.education = [
            Education(**education) for education in translated_json["education"]
        ]

    if job_description:
        print(job_description)
        cv_data.skills = highlight_skills(cv_data.skills, job_description)

    if extra_profile_text:
        cv_data.profile_texts.append(extra_profile_text)

    cv_id = save_cv_to_db(
        cv_data,
        user_uuid=source_user_id,
        user_name=source_user_data["full_name"],
        is_source=False,
    )

    db = get_db()
    with db.cursor() as cur:
        # Base CV
        query = """
            UPDATE cv
            SET handler_id = %s, job_name = %s
            WHERE id = %s;
        """
        cur.execute(
            query,
            (contact_user_id, job_name, cv_id),
        )
        db.commit()

    # Send the success response
    return jsonify({"success": True, "cv_id": cv_id})


@api_bp.route("/cv/<id>", methods=["PATCH"])
@auth_required(modes=["admin"])
def edit_targeted_cv(id):
    """Used by admins to edit CVs"""

    cv_data = CV_data(**json.loads(request.values["cv_json"]))
    contact_id = request.values["contact_id"]

    # Edit basic info
    db = get_db()
    with db.cursor() as cur:
        # Base CV
        query = """
            UPDATE cv
            SET name = %s, title = %s, handler_id = %s
            WHERE id = %s;
        """
        cur.execute(
            query,
            (cv_data.name, cv_data.title, contact_id, id),
        )

    replace_cv_data(id, cv_data)

    # Send the success response
    return jsonify({"success": True})


@api_bp.route("/targeted-cv/<id>", methods=["DELETE"])
@auth_required(modes=["admin"])
def delete_targeted_cv(id):
    """Used by admins to delete a targeted CV"""

    db = get_db()
    with db.cursor() as cur:
        query = """
            DELETE FROM cv
            WHERE id = %s
        """

        cur.execute(
            query,
            (id,),
        )

    db.commit()

    # Send the success response
    return jsonify({"success": True})
