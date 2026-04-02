from flask import session, jsonify
from flask_bcrypt import Bcrypt
from functools import wraps
from psycopg2.extensions import AsIs
import random
import math
import fitz
from app.db import get_db

# Bcrypt for password hashing
bcrypt = Bcrypt()

# Define allowed file extensions
ALLOWED_EXTENSIONS = {"pdf"}


def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


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


def generate_pin():
    """
    Generates a random 6-digit pin code
    """

    digits = [i for i in range(0, 10)]

    random_str = ""

    for i in range(6):
        index = math.floor(random.random() * 10)
        random_str += str(digits[index])

    ## displaying the random string
    return random_str


def parse_pdf(file):
    """Reads a PDF file from the local server and extracts all text."""
    try:
        doc = fitz.open(file)
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return None
