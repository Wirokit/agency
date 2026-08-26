import os
from flask import Flask, jsonify
from psycopg2 import Error
from app.db import close_db, init_db
from .routes.api import api_bp
from .routes.auth import auth_bp
from .routes.views import views_bp
from .services.utils import bcrypt
from datetime import date


def handle_db_error(e):
    """Handles psycopg2 errors"""
    print(f"Database error: {e}")
    return jsonify({"error": "A database error occurred"}), 500


def format_cv_date(date_str: str, is_year_only: bool):
    if not date_str:
        return ""

    date_obj = date.fromisoformat(date_str)

    if is_year_only:
        return date_obj.strftime("%Y")
    else:
        return date_obj.strftime("%m/%Y")


def get_cv_date_part(date_str: str, part):
    if not date_str:
        return ""

    date_obj = date.fromisoformat(date_str)

    if part == "m":
        return date_obj.strftime("%m")
    elif part == "y":
        return date_obj.strftime("%Y")
    else:
        return Error("Invalid date part")


def create_app(config):
    app = Flask(__name__)

    app.config.from_mapping(config)

    # Register custom jinja filters
    app.jinja_env.filters["cv_date"] = format_cv_date
    app.jinja_env.filters["cv_date_part"] = get_cv_date_part

    app.config["BASE_DIR"] = os.path.dirname(os.path.abspath(__file__))
    app.config["UPLOAD_FOLDER"] = os.path.join(app.config["BASE_DIR"], "static/uploads")
    app.config["PRIVACY_POLICY_PATH"] = os.path.join(
        app.config["BASE_DIR"], "static/privacy_statement.html"
    )

    # Initialize bcrypt
    bcrypt.init_app(app)

    # Listen to DB errors
    app.register_error_handler(Error, handle_db_error)

    # Initialize the DB
    init_db(app)

    # Tell Flask to run close_db after every request
    app.teardown_appcontext(close_db)

    # Ensure the upload folder exists
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(views_bp)

    return app
