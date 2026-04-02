from flask import Blueprint, render_template, session, request, redirect
from .route_utils import auth_required, get_cv_by_pin, get_user_record
import os
import psycopg2
from psycopg2.extras import register_uuid

bp_name = "views"

# Define the Blueprint
views_bp = Blueprint(bp_name, __name__)


@views_bp.before_request
def before_request():
    """Serve password update page if change is required. If user is not logged in, redirect to login."""

    if "user_id" in session:
        user_record = get_user_record(
            session["user_id"],
            "require_pw_update",
        )

        if user_record[0]:
            return render_template("views/update_pw.html", forced=True)
    elif "pin_code" not in session and request.path != "/login":
        session["redirect_url"] = request.path
        return redirect("/login")


@views_bp.route("/login", methods=["GET"])
def serve_login():
    """Serves the login page to the frontend."""

    if "user_id" in session or "pin_code" in session:
        return redirect(session["redirect_url"] if "redirect_url" in session else "")

    return render_template("login.html")


@views_bp.route("/", methods=["GET"])
@auth_required(modes=["admin", "pin_user"])
def serve_landing():
    """Serves the login and upload pages to the frontend."""

    html_file = "views/"

    if "user_id" in session:
        html_file += "upload_page.html"
    elif "pin_code" in session:
        cv_record = get_cv_by_pin(session["pin_code"])
        if not cv_record["date_uploaded"]:
            html_file += "pin_upload.html"
        else:
            return serve_cv(str(cv_record["id"]))

    # Send the html file
    return render_template(html_file)


@views_bp.route("/view", methods=["GET"])
@auth_required(modes=["admin"])
def serve_cv_list():
    """Serves the CV list page to the frontend."""

    return render_template("views/cv_list.html")


@views_bp.route("/view/<cv_id>", methods=["GET"])
@auth_required(modes=["admin", "pin_user"])
def serve_cv(cv_id):
    """Serves the CV to the frontend."""
    """VERSION 2 - All CV data is in JSON format rather than a html file"""

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
        cur.execute(query, (cv_id,))

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
        if "pin_code" in session:
            user_type = "pin"
        elif "user_id" in session:
            user_type = "admin"

        return render_template(
            "views/cv_view.html",
            cv_id=cv_id,
            json=json,
            contact=contact,
            user_type=user_type,
        )
    except Exception as e:
        print(f"Error serving file: {e}")
        return "An error occurred.", 500
