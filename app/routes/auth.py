from flask import Blueprint, jsonify, request, session
from app.db import get_db
from app.services.utils import (
    bcrypt,
)
from models import UserType, get_user_type_by_id
from .route_utils import auth_required, get_user_by_id, get_user_by_username

# Define the Blueprint
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def check_login():
    """Start a login session if username and password are correct"""

    # Ensure that data was sent
    if not request.values["user"] or not request.values["password"]:
        return jsonify({"success": False, "error": "Empty body."}), 400

    # Get db entry based on given user id
    user_record = get_user_by_username(
        request.values["user"], "id, password_hash, full_name, user_type_id"
    )

    # Check that password matches
    if user_record:
        hashed_password = user_record["password_hash"]

        # Compare passwords
        match = bcrypt.check_password_hash(hashed_password, request.values["password"])

        if match:
            session["user_id"] = user_record["id"]
            session["user_name"] = user_record["full_name"]
            session["user_type"] = get_user_type_by_id(
                user_record["user_type_id"]
            ).value
            return jsonify({"success": True, "data": {"user": request.values["user"]}})
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
            SELECT id, full_name FROM users
            WHERE pin_code IS NOT NULL AND pin_code = %s
        """
        cur.execute(query, (request.values["pin"],))
        result = cur.fetchone()

    db.rollback()

    if not result:
        return jsonify({"success": False, "error": "Invalid PIN."}), 404

    session["user_id"] = result["id"]
    session["user_name"] = result["full_name"]
    session["user_type"] = UserType.EXTERNAL.value

    return jsonify({"success": True})


@auth_bp.route("/password", methods=["UPDATE"])
@auth_required(modes=["admin", "internal"])
def update_password():
    """
    Update a user's password
    """

    # Ensure that data was sent
    if not request.values["old_password"] or not request.values["new_password"]:
        return jsonify({"success": False, "error": "Empty body."}), 400

    # Get db entry based on logged in user
    user_record = get_user_by_id(session["user_id"], "password_hash")

    # Check that user exists
    if not user_record:
        return jsonify({"success": False, "error": "Not logged in."})

    old_hashed_password = user_record["password_hash"]

    # Check that old password matches
    match = bcrypt.check_password_hash(
        old_hashed_password, request.values["old_password"]
    )

    if not match:
        return jsonify({"success": False, "error": "Current password is incorrect."})

    db = get_db()
    with db.cursor() as cur:
        query = """
            UPDATE users
            SET password_hash = %s, require_pw_update = false
            WHERE id = %s
        """
        cur.execute(
            query,
            (
                bcrypt.generate_password_hash(request.values["new_password"]).decode(
                    "utf-8"
                ),
                session["user_id"],
            ),
        )
        db.commit()

    # Send the success response
    return jsonify({"success": True})
