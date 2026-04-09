from flask import session, jsonify
from functools import wraps
from psycopg2.extensions import AsIs
from app.db import get_db

"""
  Utility functions that require session variables and/or a database connection.
"""


def verify_admin():
    if "user_id" not in session:
        return False

    db = get_db()  # Get connection from pool
    with db.cursor() as cur:
        query = "SELECT is_disabled FROM users WHERE id = %s"
        cur.execute(
            query,
            (session["user_id"],),
        )
        user_record = cur.fetchone()

    if not user_record:
        return False
    elif user_record["is_disabled"]:
        return False

    return True


def verify_pin():
    if "pin_code" not in session:
        return False

    db = get_db()  # Get connection from pool
    with db.cursor() as cur:
        # Fetch a db entry based on provided PIN
        query = """
            SELECT * FROM cv
            WHERE pin_code IS NOT NULL AND pin_code = %s
        """
        cur.execute(query, (session.get("pin_code"),))

        result = cur.fetchone()

    if not result:
        return False

    return True


def auth_required(modes):
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            success = False
            if "admin" in modes and verify_admin():
                success = True
            if "pin_user" in modes and verify_pin():
                success = True

            if not success:
                return jsonify({"error": "Unauthorized"}), 401
            return f(*args, **kwargs)

        return decorated

    return wrapper


def get_user_record(user, column="*"):
    db = get_db()  # Get connection from pool
    with db.cursor() as cur:
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

    return user_record


def get_cv_by_pin(pin_code):
    db = get_db()  # Get connection from pool
    with db.cursor() as cur:
        # Fetch a db entry based on provided user id
        query = """
            SELECT id, data_owner, date_uploaded FROM cv
            WHERE pin_code IS NOT NULL AND pin_code = %s
        """
        cur.execute(
            query,
            (pin_code,),
        )

        cv_record = cur.fetchone()

    return cv_record
