from flask import session, jsonify
from functools import wraps
from psycopg2.extensions import AsIs
from app.db import get_db
from models import UserType

"""
  Utility functions that require session variables and/or a database connection.
"""


def auth_required(modes):
    def wrapper(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            success = True

            db = get_db()  # Get connection from pool
            with db.cursor() as cur:
                query = """
                    SELECT u.is_disabled, t.user_type_name
                    FROM users u
                    JOIN user_types t USING (user_type_id)
                    WHERE u.id = %s
                """
                cur.execute(
                    query,
                    (session["user_id"],),
                )
                user_record = cur.fetchone()

            db.rollback()

            # Valid user check
            if not user_record:
                success = False
            elif user_record["is_disabled"]:
                success = False

            # User type check
            if (
                "all" not in modes
                and UserType(user_record["user_type_name"]).value not in modes
            ):
                success = False

            if not success:
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


def get_user_by_pin(pin_code):
    db = get_db()  # Get connection from pool
    with db.cursor() as cur:
        # Fetch a db entry based on provided user id
        query = """
            SELECT id, full_name FROM external_talent
            WHERE pin_code IS NOT NULL AND pin_code = %s
        """
        cur.execute(
            query,
            (pin_code,),
        )

        cv_record = cur.fetchone()

    db.rollback()

    return cv_record


def get_targeted_cvs_by_id(user_id):
    db = get_db()
    with db.cursor() as cur:
        query = """
            SELECT id, date_created, job_identifier FROM targeted_cv
            WHERE owner_id = %s
            ORDER BY date_created DESC
        """
        cur.execute(
            query,
            (user_id,),
        )

        cv_list = cur.fetchall()

    db.rollback()

    return cv_list
