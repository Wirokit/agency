import os
from flask import Flask
from app.db import close_db, init_db
from .routes.api import api_bp
from .routes.auth import auth_bp
from .routes.views import views_bp
from .routes.route_utils import bcrypt


def create_app():
    app = Flask(__name__)

    app.config.from_mapping(
        SECRET_KEY=os.environ["SECRET_FLASK_KEY"],
        MAX_CONTENT_LENGTH=50 * 1024 * 1024,  # Set a max file size (e.g., 50MB)
    )

    bcrypt.init_app(app)

    app.config["DATABASE_URL"] = (
        f"postgresql://{os.environ["RDS_USERNAME"]}:{os.environ["RDS_PASSWORD"]}@{os.environ["RDS_HOSTNAME"]}:{os.environ["RDS_PORT"]}/{os.environ["RDS_DB_NAME"]}"
    )
    app.config["BASE_DIR"] = os.path.dirname(os.path.abspath(__file__))
    app.config["UPLOAD_FOLDER"] = os.path.join(app.config["BASE_DIR"], "static/uploads")
    app.config["PRIVACY_POLICY_PATH"] = os.path.join(
        app.config["BASE_DIR"], "static/privacy_statement.html"
    )

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
