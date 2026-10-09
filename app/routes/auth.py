from flask import Blueprint, jsonify, request, session
from app.db import get_db
from app.services.utils import (
    bcrypt,
)
from models import AuthType, get_user_type_by_id
from .route_utils import (
    auth_required,
    get_user_by_id,
    get_user_by_username,
    valid_csrf_token,
)

# Define the Blueprint
auth_bp = Blueprint("auth", __name__)


@auth_bp.after_request
def prevent_auth_caching(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@auth_bp.route("/login", methods=["POST"])
def check_login():
    """Start a login session if username and password are correct"""

    # Ensure that data was sent
    if not request.form.get("user") or not request.form.get("password"):
        return jsonify({"success": False, "error": "Empty body."}), 400

    # Get db entry based on given user id
    user_record = get_user_by_username(
        request.form["user"],
        "id, password_hash, full_name, user_type_id, is_disabled, session_version",
    )

    # Check that password matches
    if (
        user_record
        and not user_record["is_disabled"]
        and user_record["user_type_id"] in (1, 2)
        and user_record["password_hash"]
    ):
        hashed_password = user_record["password_hash"]

        # Compare passwords
        match = bcrypt.check_password_hash(hashed_password, request.form["password"])

        if match:
            redirect_url = session.get("redirect_url")
            session.clear()
            if redirect_url:
                session["redirect_url"] = redirect_url
            session.permanent = True
            session["user_id"] = user_record["id"]
            session["user_name"] = user_record["full_name"]
            session["session_version"] = user_record["session_version"]
            session["user_type"] = get_user_type_by_id(
                user_record["user_type_id"]
            ).value
            return jsonify({"success": True, "data": {"user": request.form["user"]}})
        else:
            return jsonify({"success": False})
    else:
        return jsonify({"success": False})


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """End a login session"""

    session.clear()

    return jsonify({"success": True})


@auth_bp.route("/pin-login", methods=["POST"])
def check_pin():
    """Start a pin login session if pin is valid"""

    # Ensure that data was sent
    if not request.values["pin"]:
        return jsonify({"success": False, "error": "Empty body."}), 400

    db = get_db()
    with db.cursor() as cur:
        # Fetch a db entry based on provided PIN
        query = """
            SELECT u.id, u.full_name, u.session_version FROM users u
            JOIN user_types t USING (user_type_id)
            WHERE u.pin_code IS NOT NULL AND u.pin_code = %s
                AND u.is_disabled = false AND t.user_type_name = %s
        """
        cur.execute(query, (request.values["pin"], AuthType.EXTERNAL.value))
        result = cur.fetchone()

    db.rollback()

    if not result:
        return jsonify({"success": False, "error": "Invalid PIN."}), 404

    session.clear()
    session.permanent = True
    session["user_id"] = result["id"]
    session["user_name"] = result["full_name"]
    session["user_type"] = AuthType.EXTERNAL.value
    session["session_version"] = result["session_version"]

    return jsonify({"success": True})


@auth_bp.route("/password", methods=["UPDATE"])
@auth_required(modes=[AuthType.ADMIN, AuthType.INTERNAL])
def update_password():
    """
    Update a user's password
    """

    # Ensure that data was sent
    if not valid_csrf_token():
        return jsonify({"success": False, "error": "Invalid CSRF token."}), 403

    old_password = request.form.get("old_password")
    new_password = request.form.get("new_password")
    if not old_password or not new_password:
        return jsonify({"success": False, "error": "Empty body."}), 400

    if not 12 <= len(new_password) <= 64 or len(new_password.encode("utf-8")) > 72:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "New password must be 12-64 characters and at most 72 UTF-8 bytes.",
                }
            ),
            400,
        )

    if new_password == old_password:
        return jsonify({"success": False, "error": "Choose a different password."}), 400

    # Get db entry based on logged in user
    user_record = get_user_by_id(session["user_id"], "password_hash")

    # Check that user exists
    if not user_record or not user_record["password_hash"]:
        return jsonify({"success": False, "error": "Not logged in."}), 401

    old_hashed_password = user_record["password_hash"]

    # Check that old password matches
    match = bcrypt.check_password_hash(old_hashed_password, old_password)

    if not match:
        return (
            jsonify({"success": False, "error": "Current password is incorrect."}),
            400,
        )

    db = get_db()
    with db.cursor() as cur:
        query = """
            UPDATE users
            SET password_hash = %s, require_pw_update = false,
                session_version = session_version + 1
            WHERE id = %s AND session_version = %s AND password_hash = %s
                AND is_disabled = false
            RETURNING session_version
        """
        cur.execute(
            query,
            (
                bcrypt.generate_password_hash(new_password).decode("utf-8"),
                session["user_id"],
                session["session_version"],
                old_hashed_password,
            ),
        )
        updated = cur.fetchone()
        if not updated:
            db.rollback()
            session.clear()
            return jsonify({"success": False, "error": "Please log in again."}), 401
        db.commit()

    session["session_version"] = updated["session_version"]
    session.pop("csrf_token", None)
    # Send the success response
    return jsonify({"success": True})
