import os
from flask import Flask, jsonify
from psycopg2 import Error
from app.db import close_db, init_db
from .routes.api import api_bp
from .routes.auth import auth_bp
from .routes.views import views_bp
from .services.utils import bcrypt


def handle_db_error(e):
    """Handles psycopg2 errors"""
    print(f"Database error: {e}")
    return jsonify({"error": "A database error occurred"}), 500


def create_app(config):
    app = Flask(__name__)

    app.config.from_mapping(config)

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
