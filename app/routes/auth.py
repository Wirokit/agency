from flask import Blueprint, jsonify, request, session
from .route_utils import (
    bcrypt,
    auth_required,
    get_user_record,
)
import os
import psycopg2
from psycopg2.extras import RealDictCursor

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
        hashed_password = user_record[0]

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

    session["pin_user"] = result["data_owner"]
    session["pin_code"] = request.values["pin"]

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

    old_hashed_password = user_record[0]

    # Check that old password matches
    match = bcrypt.check_password_hash(
        old_hashed_password, request.values["old_password"]
    )

    if not match:
        return jsonify({"success": False, "error": "Current password is incorrect."})

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
