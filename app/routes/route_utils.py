from flask import session, jsonify
from functools import wraps
from psycopg2.extensions import AsIs
from app.db import get_db
from models import AuthType
import uuid

"""
  Utility functions that require session variables and/or a database connection.
"""


def get_authenticated_user():
    """Validate the session against the account's current status and role."""
    if not session.get("user_id") or not session.get("user_type"):
        if "user_id" in session or "user_type" in session:
            session.clear()
        return None

    db = get_db()
    with db.cursor() as cur:
        query = """
            SELECT u.is_disabled, u.require_pw_update, t.user_type_name
            FROM users u
            JOIN user_types t USING (user_type_id)
            WHERE u.id = %s
        """
        cur.execute(query, (session["user_id"],))
        user_record = cur.fetchone()

    db.rollback()

    if (
        not user_record
        or user_record["is_disabled"]
        or session["user_type"] != user_record["user_type_name"]
    ):
        session.clear()
        return None

    return user_record


def auth_required(modes: list[AuthType]):
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user_record = get_authenticated_user()
            if not user_record:
                return jsonify({"error": "Unauthorized"}), 401

            current_role = AuthType(user_record["user_type_name"])
            if AuthType.ALL not in modes and current_role not in modes:
                return jsonify({"error": "Unauthorized"}), 401

            return f(*args, **kwargs)

        return decorated

    return wrapper


def get_user_by_id(user_id, column="*"):
    db = get_db()  # Get connection from pool
    with db.cursor() as cur:
        # Fetch a db entry based on provided user id
        query = "SELECT %s FROM users WHERE id = %s"
        cur.execute(
            query,
            (
                AsIs(column),
                user_id,
            ),
        )

        user_record = cur.fetchone()

    db.rollback()

    return user_record


def get_user_by_username(username, column="*"):
    db = get_db()  # Get connection from pool
    with db.cursor() as cur:
        # Fetch a db entry based on provided user id
        query = "SELECT %s FROM users WHERE username = %s"
        cur.execute(
            query,
            (
                AsIs(column),
                username,
            ),
        )

        user_record = cur.fetchone()

    db.rollback()

    return user_record


def get_contact_users():
    db = get_db()
    with db.cursor() as cur:
        query = """
            SELECT id, full_name FROM users
            WHERE user_type_id = 1
        """
        cur.execute(query)
        contact_list = cur.fetchall()

    db.rollback()

    return contact_list


def log_cv_opened_by_guest(cv_id):
    db = get_db()
    with db.cursor() as cur:
        query = """
            UPDATE cv
            SET times_opened_by_guests = times_opened_by_guests + 1
            WHERE id = %s;
        """
        cur.execute(
            query,
            (cv_id,),
        )

    db.commit()


def calc_user_expiration_days(user_id):
    db = get_db()
    with db.cursor() as cur:
        query = """
            SELECT
                EXTRACT(DAY FROM (
                    GREATEST(
                        users.created_at,
                        COALESCE(MAX(cv.date_updated), users.created_at)
                    ) + INTERVAL '14 days' - NOW()
                )) AS days_remaining
            FROM users
            LEFT JOIN cv ON cv.owner_id = users.id
            WHERE users.id = %s
            GROUP BY users.id;
        """
        cur.execute(
            query,
            (user_id,),
        )
        response = cur.fetchone()

        db.rollback()

        return response["days_remaining"]


def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False
