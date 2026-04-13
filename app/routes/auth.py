from flask import Blueprint, jsonify, request, session
from app.db import get_db
from app.services.utils import (
    bcrypt,
)
from .route_utils import auth_required, get_user_record

# Define the Blueprint
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def check_login():
    """Start a login session if username and password are correct"""

    # Ensure that data was sent
    if not request.values["user"] or not request.values["password"]:
        return jsonify({"success": False, "error": "Empty body."}), 400

    # Get db entry based on given user id
    user_record = get_user_record(request.values["user"], "password_hash")

    # Check that password matches
    if user_record:
        hashed_password = user_record["password_hash"]

        # Compare passwords
        match = bcrypt.check_password_hash(hashed_password, request.values["password"])

        if match:
            session["user_id"] = request.values["user"]
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
            SELECT id, data_owner FROM cv
            WHERE pin_code IS NOT NULL AND pin_code = %s
        """
        cur.execute(query, (request.values["pin"],))
        result = cur.fetchone()

    db.rollback()

    if not result:
        return jsonify({"success": False, "error": "Invalid PIN."}), 404

    session["pin_user"] = result["data_owner"]
    session["pin_code"] = request.values["pin"]
    session["cv_id"] = str(request.values["id"])

    return jsonify({"success": True, "data": result})


@auth_bp.route("/password", methods=["UPDATE"])
@auth_required(modes=["admin"])
def update_password():
    """
    Update a user's password
    """

    # Ensure that data was sent
    if not request.values["old_password"] or not request.values["new_password"]:
        return jsonify({"success": False, "error": "Empty body."}), 400

    # Get db entry based on logged in user
    user_record = get_user_record(session["user_id"], "password_hash")

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
