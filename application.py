# Initial file by Gemini
import os
import uuid
from flask import Flask, request, jsonify, send_from_directory, session
from werkzeug.utils import secure_filename
from google import genai
from cv_generator import generate_professional_cv
import boto3
import botocore
import psycopg2
from psycopg2.extensions import AsIs
from psycopg2.extras import register_uuid, RealDictCursor
import json
import threading

# --- Environment ---
""" from dotenv import load_dotenv

load_dotenv() """

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

# Create a Gemini client
geminicli = genai.Client()
prompt = open("prompt.txt", "r").read()

# Create an S3 client.
s3 = boto3.client("s3")


# Start cleanup script - Runs every 24h
def cleanup():
    # Don't run cleanup in development
    if os.environ.get("DEBUG_MODE") == "TRUE":
        return

    print("Starting cleanup process")
    records_cleaned = 0

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

    # Fetch a db entry based on provided user id
    cur.execute(
        f"SELECT id FROM cv WHERE date_created < now() - interval '{os.environ.get('RETENTION_DAYS')}' day"
    )

    expired_records = cur.fetchall()
    for record in expired_records:
        fileName = f"{str(record[0])}.html"
        # Delete from S3
        s3.delete_object(
            Bucket=os.environ.get("S3_BUCKET_NAME"), Key=f"cv_html/{fileName}"
        )
        # Delete from local memory
        if os.path.exists(f"processed_files/{fileName}"):
            os.remove(f"processed_files/{fileName}")
        # Delete DB record
        query = "DELETE FROM cv WHERE id = %s"
        cur.execute(query, (record))
        records_cleaned += 1

    # Commit changes
    conn.commit()

    # Close connection
    cur.close()
    conn.close()

    print(f"Cleaned up {records_cleaned} records")
    threading.Timer(86400, cleanup).start()


# Start cleanup cycle on boot
cleanup()


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


def session_is_valid(session):
    valid_session = False

    user_id = session.get("user_id")
    if user_id:
        user_data = get_user_record(user_id, "is_disabled")
        if user_data and not user_data[0]:
            valid_session = True

    return valid_session


# --- Views ---


@application.route("/", methods=["GET"])
def serve_html():
    """Serves the login and upload pages to the frontend."""

    html_path = ""
    html_file = ""

    valid_session = session_is_valid(session)
    if not valid_session:
        html_path = os.path.join(VIEW_DIR, "login.html")
        html_file = "login.html"
    else:
        html_path = os.path.join(VIEW_DIR, "upload_page.html")
        html_file = "upload_page.html"

    # Check if html exists
    if not os.path.exists(html_path):
        return "Frontend ({html_file}) not found.", 404

    # Send the html file
    return send_from_directory(VIEW_DIR, html_file)


@application.route("/view", methods=["GET"])
def cv_list():
    """Serves the CV list page to the frontend."""

    # Ensure user is logged in
    valid_session = session_is_valid(session)
    if not valid_session:
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    return send_from_directory(
        VIEW_DIR,
        "cv_list.html",
        as_attachment=False,  # Set to True to force download
    )


@application.route("/view/<file_id>", methods=["GET"])
def view_file(file_id):
    """Serves the CV to the frontend."""

    # Ensure user is logged in
    valid_session = session_is_valid(session)
    if not valid_session:
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    try:
        # Securely build the filename
        filename = f"{secure_filename(file_id)}.html"

        # Check if the file exists
        filepath = os.path.join(PROCESSED_FOLDER, filename)
        if not os.path.exists(filepath):
            # Download the file from S3
            s3.download_file(
                os.environ.get("S3_BUCKET_NAME"), f"cv_html/{filename}", filepath
            )

        # Send the file from the 'processed_files' directory
        return send_from_directory(
            PROCESSED_FOLDER,
            filename,
            as_attachment=False,  # Set to True to force download
        )
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return "File not found.", 404
        else:
            print(f"Error serving file: {e}")
            return "An error occurred.", 500
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
            return jsonify({"success": True})
        else:
            return jsonify({"success": False})
    else:
        return jsonify({"success": False})


@application.route("/api/cv", methods=["GET"])
def getCVList():
    """Returns a list of all CVs"""

    # Ensure user is logged in
    valid_session = session_is_valid(session)
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
        SELECT id, data_owner, date_created FROM cv
        ORDER BY date_created DESC
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
    valid_session = session_is_valid(session)
    if not valid_session:
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    # 1. Check if a file was sent
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file part in the request."}), 400

    # Get contact data for the current user
    contact_data = get_user_record(
        session.get("user_id"), "contact_name, contact_email, contact_phone"
    )

    file = request.files["file"]
    first_name_only = request.values["firstNameOnly"]
    keyword_list = request.values["keywordList"]
    profile_text = request.values["profileText"]

    # 2. Check if the user selected a file
    if file.filename == "":
        return jsonify({"success": False, "error": "No file selected."}), 400

    # 3. Check if the file is an allowed type (PDF)
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

    # Prompt settings
    prompt_preferences = ""
    if first_name_only == "true":
        prompt_preferences += " Only take the first name."
    if keyword_list != "":
        keyword_list = keyword_list.replace("```", "")
        prompt_preferences += f" Highlight skills relevant for the following job: ```\n{keyword_list}\n```"
    else:
        prompt_preferences += " Leave the 'highlightSkills' list empty."

    updated_prompt = prompt.replace("{p}", prompt_preferences)

    if file:
        # 4. Secure the filename (prevents directory traversal attacks)
        original_filename = secure_filename(file.filename)

        # 5. Save the original file
        original_filepath = os.path.join(UPLOAD_FOLDER, original_filename)
        file.save(original_filepath)

        # 6. Generate a unique ID for the processed file
        file_id = str(uuid.uuid4())
        processed_filename = f"{file_id}.html"
        processed_filepath = os.path.join(PROCESSED_FOLDER, processed_filename)

        # 7. --- PDF PROCESSING LOGIC ---
        try:
            pdf_to_process = geminicli.files.upload(file=original_filepath)
            response = geminicli.models.generate_content(
                model="gemini-2.5-flash",
                contents=[updated_prompt, pdf_to_process],
                config={
                    "response_mime_type": "application/json",
                },
            )

            result_json = response.text

            # Ensure data is a dictionary
            if isinstance(result_json, str):
                json_data = json.loads(result_json)
            else:
                json_data = result_json

            generate_professional_cv(
                json_data,
                contact_name=contact_data[0],
                contact_email=contact_data[1],
                contact_phone=contact_data[2],
                output_filename=processed_filepath,
                profile_extra_text=profile_text,
            )

            # Upload HTML file to S3
            with open(processed_filepath, "rb") as data:
                s3.upload_fileobj(
                    data,
                    os.environ.get("S3_BUCKET_NAME"),
                    f"cv_html/{processed_filename}",
                )

            # Log new CV to the database
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

            # Store CV information in the DB
            query = """
                INSERT INTO cv (id, data_owner, date_created)
                VALUES (%s, %s, now())
            """
            cur.execute(query, (file_id, json_data["name"]))
            conn.commit()

            # Close connection
            cur.close()
            conn.close()

            # --- End of PDF processing logic ---
        except Exception as e:
            # Check for gemini overload issues
            if "The model is overloaded" in str(e):
                return (
                    jsonify(
                        {
                            "success": False,
                            "error": "Gemini model is overloaded. Please try again.",
                        }
                    ),
                    500,
                )

            # Catch other potential errors
            print(f"An unexpected error occurred: {e}")
            return (
                jsonify(
                    {"success": False, "error": "An unexpected server error occurred."}
                ),
                500,
            )

        # 8. Build the URL for the new file
        # This URL points to our '/view/' endpoint below
        new_url = f"/view/{file_id}"

        # 9. Send the success response
        return jsonify({"success": True, "url": new_url})


@application.route("/api/cv", methods=["DELETE"])
def delete_file():
    """
    Handles file deletion.
    """

    # Ensure user is logged in
    valid_session = session_is_valid(session)
    if not valid_session:
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    cv_id_list = json.loads(request.values["cvListJson"])

    try:
        # Delete from S3 and local
        for id in cv_id_list:
            # S3
            s3.delete_object(
                Bucket=os.environ.get("S3_BUCKET_NAME"), Key=f"cv_html/{id}.html"
            )

            # Local
            if os.path.exists(f"processed_files/{id}.html"):
                os.remove(f"processed_files/{id}.html")

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


# --- Run the Application ---

if __name__ == "__main__":
    # Run the app.
    # 'debug=True' is great for development as it auto-reloads.
    application.run(debug=os.environ.get("DEBUG_MODE") == "TRUE", host="0.0.0.0")
