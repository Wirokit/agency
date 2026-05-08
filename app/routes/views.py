from flask import Blueprint, jsonify, render_template, session, request, redirect
from app.db import get_db
from app.types.user import UserType, get_user_type_by_id
from .route_utils import auth_required, get_targeted_cvs_by_id, get_user_by_id

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
        db = get_db()
        with db.cursor() as cur:
            me_query = """
                SELECT u.id, u.full_name, u.title, u.office, t.user_type_name
                FROM users u
                JOIN user_types t USING (user_type_id)
                WHERE u.id = %s
            """
            cur.execute(me_query, (session["user_id"],))
            me_result = cur.fetchone()

            internal_query = """
                SELECT u.id, u.full_name, u.title, u.office, t.user_type_name
                FROM users u
                JOIN user_types t USING (user_type_id)
                WHERE u.id != %s AND u.is_disabled is false AND user_type_id != 3
                ORDER BY u.full_name ASC
            """
            cur.execute(internal_query, (session["user_id"],))
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

        return render_template(
            "views/landing.html",
            my_profile=me_result,
            internal_users=internal_result,
            external_users=external_result or [],
        )
    else:
        return serve_profile()


@views_bp.route("/cv/<cv_id>", methods=["GET"])
@auth_required(modes=["all"])
def serve_targeted_cv(cv_id):
    """Serves a targeted CV to the frontend."""

    db = get_db()
    with db.cursor() as cur:
        query = """
            SELECT
                cv.owner_id,
                owner.full_name AS owner_name,
                cv.cv_json,
                handler.full_name AS handler_name,
                handler.email AS handler_email,
                handler.phone_num AS handler_phone
            FROM targeted_cv cv
            JOIN users handler ON cv.handler_id = handler.id
            JOIN users owner ON cv.owner_id = owner.id
            WHERE cv.id = %s
        """
        cur.execute(query, (cv_id,))
        result = cur.fetchone()

    db.rollback()

    json = result["cv_json"]
    contact = {
        "name": result["handler_name"],
        "email": result["handler_email"],
        "phone": result["handler_phone"],
    }

    return render_template(
        "views/targeted_cv_view.html",
        is_users_cv=session["user_id"] == result["owner_id"],
        owner_name=result["owner_name"],
        owner_id=result["owner_id"],
        cv_id=cv_id,
        cv_data=json,
        contact=contact,
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
        "full_name, title, office, cv_data, user_type_id, pin_code, created_at",
    )
    user_type = get_user_type_by_id(user_data["user_type_id"])

    # Internal non-admin users can not view external users
    if (
        UserType(session["user_type"]) is UserType.INTERNAL
        and user_type is UserType.EXTERNAL
    ):
        return jsonify({"success": False, "error": "Access forbidden."}), 403

    # Get targeted CVs for the target user
    targeted_cv_list = get_targeted_cvs_by_id(user_id)

    return render_template(
        "views/user_profile.html",
        user_type=user_type.value,
        user_id=user_id,
        user_name=user_data["full_name"],
        user_title=user_data["title"] or "",
        user_office=user_data.get("office", ""),
        cv_data=user_data.get("cv_data", "{}"),
        pin_code=user_data.get("pin_code", ""),
        created_at=user_data["created_at"],
        targeted_cv_list=targeted_cv_list or [],
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
