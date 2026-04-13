from flask import Blueprint, render_template, session, request, redirect
from app.db import get_db
from .route_utils import auth_required, get_cv_by_pin, get_user_record, verify_pin

bp_name = "views"

# Define the Blueprint
views_bp = Blueprint(bp_name, __name__)


@views_bp.before_request
def before_request():
    """Serve password update page if change is required. If user is not logged in, redirect to login."""

    ignored_endpoints = ["views.serve_login", "static"]
    redirect_to_login = False

    if "user_id" in session:
        user_record = get_user_record(
            session["user_id"],
            "is_disabled, require_pw_update",
        )

        if not user_record or user_record["is_disabled"]:
            session.clear()
            redirect_to_login = True
        elif user_record["require_pw_update"]:
            return render_template("views/update_pw.html", forced=True)
    elif "pin_code" in session:
        valid_pin = verify_pin()
        if not valid_pin:
            session.clear()
            redirect_to_login = True
    elif request.endpoint not in ignored_endpoints:
        redirect_to_login = True

    if redirect_to_login:
        session["redirect_url"] = request.path
        return redirect("/login")


@views_bp.route("/login", methods=["GET"])
def serve_login():
    """Serves the login page to the frontend."""

    if "user_id" in session or "pin_code" in session:
        return redirect(session["redirect_url"] if "redirect_url" in session else "/")

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

    db = get_db()
    with db.cursor() as cur:
        query = """
            SELECT cv.cv_json, c.name, c.email, c.phone FROM cv
            JOIN contact_info c ON cv.contact_id = c.id
            WHERE cv.id = %s
        """
        cur.execute(query, (cv_id,))
        result = cur.fetchone()

    db.rollback()

    json = result["cv_json"]
    contact = {
        "name": result["name"],
        "email": result["email"],
        "phone": result["phone"],
    }

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
