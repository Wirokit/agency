from flask import Blueprint, jsonify, render_template, session, request, redirect
from app.db import get_db
from app.services.cv import (
    get_cv_data_by_id,
    get_cv_handler,
    get_cv_owner,
    get_source_cv,
    get_targeted_cvs_by_id,
)
from app.services.s3 import get_profile_img_url
from models import UserType, get_user_type_by_id
from .route_utils import auth_required, get_user_by_id

bp_name = "views"

# Define the Blueprint
views_bp = Blueprint(bp_name, __name__)


@views_bp.before_request
def before_request():
    """Serve password update page if change is required. If user is not logged in, redirect to login."""

    ignored_endpoints = ["views.serve_login", "static"]
    redirect_to_login = False

    if "user_id" in session:
        user_record = get_user_by_id(
            session["user_id"],
            "is_disabled, require_pw_update",
        )

        session["profile_img_url"] = get_profile_img_url(session["user_id"])

        if not user_record or user_record["is_disabled"]:
            session.clear()
            redirect_to_login = True
        elif (
            UserType(session["user_type"]) is not UserType.EXTERNAL
            and user_record["require_pw_update"]
        ):
            return render_template("views/update_pw.html", forced=True)
    elif request.endpoint not in ignored_endpoints:
        redirect_to_login = True

    if redirect_to_login:
        session["redirect_url"] = request.path
        return redirect("/login")


@views_bp.route("/login", methods=["GET"])
def serve_login():
    """Serves the login page to the frontend."""

    if "user_id" in session or "pin_code" in session:
        return redirect(
            session["redirect_url"]
            if "redirect_url" in session and session["redirect_url"] != "/login"
            else "/"
        )

    return render_template("login.html")


@views_bp.route("/", methods=["GET"])
@auth_required(modes=["all"])
def serve_landing():
    """Serves the login and landing pages to the frontend."""

    if UserType(session["user_type"]) in [UserType.ADMIN, UserType.INTERNAL]:
        external_result = None

        db = get_db()
        with db.cursor() as cur:
            internal_query = """
                SELECT u.id, u.full_name, u.title, u.office, t.user_type_name
                FROM users u
                JOIN user_types t USING (user_type_id)
                WHERE u.is_disabled is false AND user_type_id != 3
                ORDER BY u.full_name ASC
            """
            cur.execute(internal_query)
            internal_result = cur.fetchall()

            if UserType(session["user_type"]) is UserType.ADMIN:
                external_query = """
                    SELECT u.id, u.full_name, u.title, u.office, t.user_type_name
                    FROM users u
                    JOIN user_types t USING (user_type_id)
                    WHERE user_type_id = 3
                """
                cur.execute(external_query)
                external_result = cur.fetchall()

        db.rollback()

        for user in internal_result:
            user["profile_img_url"] = get_profile_img_url(user["id"])

        return render_template(
            "views/landing.html",
            internal_users=internal_result,
            external_users=external_result or [],
        )
    else:
        return serve_profile()


@views_bp.route("/cv/<cv_id>", methods=["GET"])
@auth_required(modes=["all"])
def serve_targeted_cv(cv_id):
    """Serves a targeted CV to the frontend."""

    cv_data = get_cv_data_by_id(cv_id)
    owner = get_cv_owner(cv_id)
    handler = get_cv_handler(cv_id)

    return render_template(
        "views/targeted_cv_view.html",
        is_users_cv=session["user_id"] == owner.id,
        owner_id=owner.id,
        cv_id=cv_id,
        cv_data=cv_data,
        contact=handler,
    )


@views_bp.route("/edit-cv/<cv_id>", methods=["GET"])
@auth_required(modes=["all"])
def serve_cv_edit(cv_id):
    """Serves a CV's edit page to the frontend."""

    owner = get_cv_owner(cv_id)
    if session["user_type"] != UserType.ADMIN and owner.id != session["user_id"]:
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    cv_data = get_cv_data_by_id(cv_id)

    return render_template(
        "views/edit_cv.html",
        is_users_cv=session["user_id"] == owner.id,
        owner_id=owner.id,
        cv_id=cv_id,
        cv_data=cv_data,
    )


@views_bp.route("/profile", methods=["GET"])
@auth_required(modes=["all"])
def serve_profile():
    """Serves the user's profile page."""

    return serve_profile_by_id(session["user_id"])


@views_bp.route("/profile/<user_id>", methods=["GET"])
@auth_required(modes=["all"])
def serve_profile_by_id(user_id):
    """Serves a specific user's profile page."""

    # If user is external, ensure the profile is theirs
    if (
        UserType(session["user_type"]) is UserType.EXTERNAL
        and user_id != session["user_id"]
    ):
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    # Get target user's info
    user_data = get_user_by_id(
        user_id,
        "full_name, title, office, user_type_id, pin_code, created_at",
    )
    user_type = get_user_type_by_id(user_data["user_type_id"])

    # Internal non-admin users can not view external users
    if (
        UserType(session["user_type"]) is UserType.INTERNAL
        and user_type is UserType.EXTERNAL
    ):
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    cv_data = get_source_cv(user_id)

    # Get targeted CVs for the target user
    targeted_cv_list = get_targeted_cvs_by_id(user_id)

    return render_template(
        "views/user_profile.html",
        user_type=user_type.value,
        user_id=user_id,
        profile_img_url=get_profile_img_url(user_id),
        user_name=user_data["full_name"],
        user_title=user_data["title"] or "",
        user_office=user_data.get("office", ""),
        cv_data=cv_data or {},
        pin_code=user_data.get("pin_code", ""),
        created_at=user_data["created_at"],
        targeted_cv_list=targeted_cv_list,
        hide_basic_info_from_cv_edit=True,
    )


@views_bp.route("/new-user", methods=["GET"])
@auth_required(modes=["admin"])
def serve_user_creation():
    """Serves the user creation page"""

    return render_template("views/create_user.html")


@views_bp.route("/new-external", methods=["GET"])
@auth_required(modes=["admin"])
def serve_extarnal_creation():
    """Serves the external talent creation page"""

    return render_template("views/create_external.html")
