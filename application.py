# Initial file by Gemini
import os
import uuid
from flask import Flask, render_template, request, jsonify, session
from werkzeug.utils import secure_filename
import psycopg2
from psycopg2.extensions import AsIs
from psycopg2.extras import register_uuid, RealDictCursor
import json
from utils import generate_pin, parse_pdf, generate_extraction_prompt, query_bedrock

# --- Environment - Only needed when running locally ---
""" from dotenv import load_dotenv

load_dotenv() """
# ---

# Create a Flask application
application = Flask(__name__, static_url_path="/static")

# Define upload and processed directories
# os.path.dirname(__file__) gets the directory this script is in
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIEW_DIR = os.path.join(BASE_DIR, "views")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
PROCESSED_FOLDER = os.path.join(BASE_DIR, "processed_files")

# Ensure these directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Application config
application.config.from_mapping(
    SECRET_KEY=os.environ["SECRET_FLASK_KEY"],
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,  # Set a max file size (e.g., 50MB)
)

# Define allowed file extensions
ALLOWED_EXTENSIONS = {"pdf"}


def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_user_record(user, column="*"):
    try:
        # Connect to an RDS database
        conn = psycopg2.connect(
            host=os.environ.get("RDS_HOSTNAME"),
            database=os.environ.get("RDS_DB_NAME"),
            user=os.environ.get("RDS_USERNAME"),
            password=os.environ.get("RDS_PASSWORD"),
            port=os.environ.get("RDS_PORT"),
        )
        cur = conn.cursor()

        # Fetch a db entry based on provided user id
        query = "SELECT %s FROM users WHERE id = %s"
        cur.execute(
            query,
            (
                AsIs(column),
                user,
            ),
        )

        user_record = cur.fetchone()

        # Close connection
        cur.close()
        conn.close()

        return user_record
    except Exception as e:
        print(f"Error fetching user: {e}")
        return None


def login_session_is_valid(session):
    valid_session = False

    user_id = session.get("user_id")
    if user_id:
        user_data = get_user_record(user_id, "is_disabled")
        if user_data and not user_data[0]:
            valid_session = True

    return valid_session


def validate_pin(session):
    pin = session.get("pin_code")
    if pin:
        # Connect to an RDS database
        conn = psycopg2.connect(
            host=os.environ.get("RDS_HOSTNAME"),
            database=os.environ.get("RDS_DB_NAME"),
            user=os.environ.get("RDS_USERNAME"),
            password=os.environ.get("RDS_PASSWORD"),
            port=os.environ.get("RDS_PORT"),
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Fetch a db entry based on provided PIN
        query = """
            SELECT id, data_owner, date_uploaded FROM cv
            WHERE pin_code IS NOT NULL AND pin_code = %s
        """
        cur.execute(query, (session.get("pin_code"),))

        result = cur.fetchone()

        # Close connection
        cur.close()
        conn.close()

        if not result:
            return False

        return result
    return False


# --- Views ---


@application.route("/", methods=["GET"])
def serve_html():
    """Serves the login and upload pages to the frontend."""

    html_file = "views/"

    valid_login_session = login_session_is_valid(session)
    pin_session = validate_pin(session)
    if not valid_login_session and not pin_session:
        html_file += "login.html"
    elif valid_login_session:
        html_file += "upload_page.html"
    else:
        if not pin_session["date_uploaded"]:
            html_file += "pin_upload.html"
        else:
            return view_file(str(pin_session["id"]))

    # Send the html file
    return render_template(html_file)


@application.route("/view", methods=["GET"])
def cv_list():
    """Serves the CV list page to the frontend."""

    # Ensure user is logged in
    valid_session = login_session_is_valid(session)
    if not valid_session:
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    return render_template("views/cv_list.html")


@application.route("/view/<file_id>", methods=["GET"])
def view_file(file_id):
    """Serves the CV to the frontend."""
    """VERSION 2 - All CV data is in JSON format rather than a html file"""

    # Ensure user is logged in
    valid_session = login_session_is_valid(session)
    pin_session = validate_pin(session)
    if not valid_session and not pin_session:
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    try:
        # Connect to an RDS database
        conn = psycopg2.connect(
            host=os.environ.get("RDS_HOSTNAME"),
            database=os.environ.get("RDS_DB_NAME"),
            user=os.environ.get("RDS_USERNAME"),
            password=os.environ.get("RDS_PASSWORD"),
            port=os.environ.get("RDS_PORT"),
        )
        cur = conn.cursor()

        # Register the UUID format for psycopg2
        register_uuid()

        query = """
            SELECT cv.cv_json, c.name, c.email, c.phone FROM cv
            JOIN contact_info c ON cv.contact_id = c.id
            WHERE cv.id = %s
        """
        cur.execute(query, (file_id,))

        result = cur.fetchone()
        json = result[0]
        contact = {
            "name": result[1],
            "email": result[2],
            "phone": result[3],
        }

        # Close connection
        cur.close()
        conn.close()

        user_type = "viewer"
        if pin_session != False:
            user_type = "pin"
        elif valid_session != False:
            user_type = "admin"

        return render_template(
            "views/cv_view.html",
            cv_id=file_id,
            json=json,
            contact=contact,
            user_type=user_type,
        )
    except Exception as e:
        print(f"Error serving file: {e}")
        return "An error occurred.", 500


# --- API Endpoints ---


@application.route("/api/login", methods=["POST"])
def check_login():
    """Start a login session if username and password are correct"""

    # Ensure that data was sent
    if not request.values["user"] or not request.values["password"]:
        return jsonify({"success": False, "error": "Empty body."}), 400

    # Get db entry based on given user id
    user_record = get_user_record(request.values["user"], "password")

    # Check that password matches
    if user_record:
        stored_password = user_record[0]

        # Compare passwords - UNHASHED
        password_correct = request.values["password"] == stored_password

        if password_correct:
            session["user_id"] = request.values["user"]
            return jsonify({"success": True, "data": {"user": request.values["user"]}})
        else:
            return jsonify({"success": False})
    else:
        return jsonify({"success": False})


@application.route("/api/logout", methods=["POST"])
def logout():
    """End a login session"""

    session.clear()

    return jsonify({"success": True})


@application.route("/api/pin-login", methods=["POST"])
def check_pin():
    """Start a pin login session if pin is valid"""

    # Ensure that data was sent
    if not request.values["pin"]:
        return jsonify({"success": False, "error": "Empty body."}), 400

    # Connect to an RDS database
    conn = psycopg2.connect(
        host=os.environ.get("RDS_HOSTNAME"),
        database=os.environ.get("RDS_DB_NAME"),
        user=os.environ.get("RDS_USERNAME"),
        password=os.environ.get("RDS_PASSWORD"),
        port=os.environ.get("RDS_PORT"),
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Fetch a db entry based on provided PIN
    query = """
        SELECT id, data_owner FROM cv
        WHERE pin_code IS NOT NULL AND pin_code = %s
    """
    cur.execute(query, (request.values["pin"],))

    result = cur.fetchone()

    # Close connection
    cur.close()
    conn.close()

    if not result:
        return jsonify({"success": False, "error": "Invalid PIN."}), 404

    session["pin_code"] = request.values["pin"]

    return jsonify({"success": True, "data": result})


@application.route("/api/cv", methods=["GET"])
def getCVList():
    """Returns a list of all CVs"""

    # Ensure user is logged in
    valid_session = login_session_is_valid(session)
    if not valid_session:
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    # Connect to an RDS database
    conn = psycopg2.connect(
        host=os.environ.get("RDS_HOSTNAME"),
        database=os.environ.get("RDS_DB_NAME"),
        user=os.environ.get("RDS_USERNAME"),
        password=os.environ.get("RDS_PASSWORD"),
        port=os.environ.get("RDS_PORT"),
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Fetch a db entry based on provided user id
    query = """
        SELECT id, data_owner, date_uploaded FROM cv
        ORDER BY date_uploaded DESC
    """
    cur.execute(query)

    result = cur.fetchall()

    # Close connection
    cur.close()
    conn.close()

    return jsonify({"success": False, "data": result})


@application.route("/api/cv", methods=["POST"])
def upload_file():
    """
    Handles file upload, processing, and returns a link to the new file.
    """

    # Ensure user is logged in
    valid_session = login_session_is_valid(session)
    if not valid_session:
        return jsonify({"success": False, "error": "Access forbidden."}), 403

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
    original_filepath = os.path.join(UPLOAD_FOLDER, original_filename)
    file.save(original_filepath)

    # Parse PDF into raw string
    cv_data = parse_pdf(original_filepath)

    # Generate prompt for the AI Model
    prompt = generate_extraction_prompt(
        cv_data, first_name_only=first_name_only == "true"
    )

    try:
        parsed_json = query_bedrock(prompt)

        ### Highlight skills based on keywords, if provided. ###
        if keyword_list != "":
            highlight_json = query_bedrock(
                f"""
                    I am going to provide a Job Description and a Master Skill List.

                    Your task is to analyze the Job Description and extract only the skills from my Master Skill List that are directly relevant or implicitly required for the role.

                    Return the extracted skill array as "highlightSkills".

                    Job Description: ""\"{keyword_list}""\"
                    Master Skill List: ""\"{json.dumps(parsed_json["skills"])}""\"
                """
            )
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

        conn = psycopg2.connect(
            host=os.environ.get("RDS_HOSTNAME"),
            database=os.environ.get("RDS_DB_NAME"),
            user=os.environ.get("RDS_USERNAME"),
            password=os.environ.get("RDS_PASSWORD"),
            port=os.environ.get("RDS_PORT"),
        )
        cur = conn.cursor()

        # Register the UUID format for psycopg2
        register_uuid()

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
                user_data[0],
            ),
        )
        conn.commit()

        # Build the URL for the new file
        # This URL points to our '/view/' endpoint below
        new_url = f"/view/{file_id}"

        # Send the success response
        return jsonify({"success": True, "url": new_url})
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An unexpected server error occurred: {e}",
                }
            ),
            500,
        )
    finally:
        # Remove original file if it exists
        if os.path.exists(original_filepath):
            os.remove(original_filepath)

        # Close the DB connection
        cur.close()
        conn.close()


# Used by users that have loggen in via PIN to upload their own CV
# Settings were previously set by admins in create_pin()
@application.route("/api/cv", methods=["UPDATE"])
def update_cv():
    # Ensure that user has logged in with a valid PIN
    pin_session = validate_pin(session)
    if not pin_session:
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    # Ensure that a file was sent
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file part in the request."}), 400

    file = request.files["file"]

    # Secure the original filename (prevents directory traversal attacks)
    original_filename = secure_filename(file.filename)

    # Save the original file
    original_filepath = os.path.join(UPLOAD_FOLDER, original_filename)
    file.save(original_filepath)

    # Fetch cv settings from the DB
    conn = psycopg2.connect(
        host=os.environ.get("RDS_HOSTNAME"),
        database=os.environ.get("RDS_DB_NAME"),
        user=os.environ.get("RDS_USERNAME"),
        password=os.environ.get("RDS_PASSWORD"),
        port=os.environ.get("RDS_PORT"),
    )
    cur = conn.cursor()

    # Register the UUID format for psycopg2
    register_uuid()

    # Fetch a db entry based on provided id
    query = """
        SELECT id, settings_json FROM cv
        WHERE pin_code = %s
    """
    cur.execute(query, (session.get("pin_code"),))

    result = cur.fetchone()
    id = result[0]
    first_name_only = result[1]["first_name_only"] or False
    keyword_list = result[1]["keyword_list"] or []
    profile_text = result[1]["profile_text"] or ""

    # Parse PDF into raw string
    cv_data = parse_pdf(original_filepath)

    # Generate prompt for the AI Model
    prompt = generate_extraction_prompt(
        cv_data, first_name_only=first_name_only == "true"
    )

    try:
        parsed_json = query_bedrock(prompt)

        ### Highlight skills based on keywords, if provided. ###
        if keyword_list != "":
            highlight_json = query_bedrock(
                f"""
                    I am going to provide a Job Description and a Master Skill List.

                    Your task is to analyze the Job Description and extract only the skills from my Master Skill List that are directly relevant or implicitly required for the role.

                    Return the extracted skill array as "highlightSkills".

                    Job Description: ""\"{keyword_list}""\"
                    Master Skill List: ""\"{json.dumps(parsed_json["skills"])}""\"
                """
            )
            parsed_json["highlightSkills"] = highlight_json["highlightSkills"]

            # Remove duplicate skills
            for skill in parsed_json["highlightSkills"]:
                if skill in parsed_json["skills"]:
                    parsed_json["skills"].remove(skill)

        # Inject custom profile text into the json object
        if profile_text != "":
            parsed_json["profileTexts"].append(profile_text)

        conn = psycopg2.connect(
            host=os.environ.get("RDS_HOSTNAME"),
            database=os.environ.get("RDS_DB_NAME"),
            user=os.environ.get("RDS_USERNAME"),
            password=os.environ.get("RDS_PASSWORD"),
            port=os.environ.get("RDS_PORT"),
        )
        cur = conn.cursor()

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
        conn.commit()

        # Send the success response
        return jsonify({"success": True})
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "An unexpected server error occurred: {e}",
                }
            ),
            500,
        )
    finally:
        # Remove original file if it exists
        if os.path.exists(original_filepath):
            os.remove(original_filepath)

        # Close the DB connection
        cur.close()
        conn.close()


@application.route("/api/pin", methods=["POST"])
def create_pin():
    """
    Creates an empty CV entry with a PIN so a CV can be uploaded by them at a later date
    """

    # Ensure user is logged in
    valid_session = login_session_is_valid(session)
    if not valid_session:
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    user_data = get_user_record(session.get("user_id"), "contact_id")

    try:
        # Connect to the RDS database
        conn = psycopg2.connect(
            host=os.environ.get("RDS_HOSTNAME"),
            database=os.environ.get("RDS_DB_NAME"),
            user=os.environ.get("RDS_USERNAME"),
            password=os.environ.get("RDS_PASSWORD"),
            port=os.environ.get("RDS_PORT"),
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)

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

        # Register the UUID format for psycopg2
        register_uuid()

        # Delete the rows with the provided IDs
        query = "INSERT INTO cv (id, data_owner, pin_code, contact_id, settings_json) VALUES (%s, %s, %s, %s, %s)"
        cur.execute(
            query,
            (
                uuid.uuid4(),
                request.values["recipientIdentifier"],
                pin,
                user_data[0],
                json.dumps(
                    {
                        "first_name_only": request.values["firstNameOnly"] == "true",
                        "keyword_list": request.values["keywordList"],
                        "profile_text": request.values["profileText"],
                    }
                ),
            ),
        )
        conn.commit()

        # Close connection
        cur.close()
        conn.close()

        # Send the success response
        return jsonify({"success": True, "pin": pin})
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return (
            jsonify(
                {"success": False, "error": "An unexpected server error occurred: {e}"}
            ),
            500,
        )


@application.route("/api/cv", methods=["DELETE"])
def delete_file():
    """
    Handles file deletion.
    """

    admin_session = login_session_is_valid(session)
    pin_session = validate_pin(session)

    cv_id_list = json.loads(request.values["cvListJson"])

    # If logged in by PIN, ensure the CV being deleted corresponds to the PIN used
    # assumes first CV if somehow multiple were sent
    if pin_session != False:
        cv_id_list = [cv_id_list[0]]
        if str(pin_session["id"]) != cv_id_list[0]:
            return jsonify({"success": False, "error": "Access forbidden."}), 403
    elif not admin_session:
        # Else, ensure the user is a logged in admin
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    try:
        # Connect to the RDS database
        conn = psycopg2.connect(
            host=os.environ.get("RDS_HOSTNAME"),
            database=os.environ.get("RDS_DB_NAME"),
            user=os.environ.get("RDS_USERNAME"),
            password=os.environ.get("RDS_PASSWORD"),
            port=os.environ.get("RDS_PORT"),
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Delete the rows with the provided IDs
        query = "DELETE FROM cv WHERE id IN %s"
        cur.execute(query, (tuple(cv_id_list),))
        conn.commit()

        # Close connection
        cur.close()
        conn.close()

        # Send the success response
        return jsonify({"success": True})
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return (
            jsonify(
                {"success": False, "error": "An unexpected server error occurred."}
            ),
            500,
        )


@application.route("/api/cv-edit", methods=["UPDATE"])
def edit_cv():
    """
    Handles json updates when admin edits the cv
    """

    # Ensure user is logged in
    valid_session = login_session_is_valid(session)
    if not valid_session:
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    cv_id = request.values["cv_id"]
    cv_json = json.loads(request.values["cv_json"])

    try:
        # Connect to the RDS database
        conn = psycopg2.connect(
            host=os.environ.get("RDS_HOSTNAME"),
            database=os.environ.get("RDS_DB_NAME"),
            user=os.environ.get("RDS_USERNAME"),
            password=os.environ.get("RDS_PASSWORD"),
            port=os.environ.get("RDS_PORT"),
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        register_uuid()

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
        conn.commit()

        # Close connection
        cur.close()
        conn.close()

        # Send the success response
        return jsonify({"success": True})
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return (
            jsonify({"success": False, "error": f"{e}"}),
            500,
        )


@application.route("/api/privacy-policy", methods=["GET"])
def get_privacy_policy():
    """
    Returns the privacy policy in HTML form.
    """

    privacy_policy = open("privacy_statement.html", "r").read()

    return privacy_policy


# --- Run the Application ---

if __name__ == "__main__":
    # Run the app.
    # 'debug=True' is great for development as it auto-reloads.
    application.run(debug=os.environ.get("DEBUG_MODE") == "TRUE", host="0.0.0.0")
