import os

# --- Environment - Only needed when running locally ---
""" from dotenv import load_dotenv

load_dotenv() """
# ---


def getConfig(testing=False):
    shared_config = {
        "MAX_CONTENT_LENGTH": 50 * 1024 * 1024  # Set a max file size (e.g., 50MB)
    }

    if testing:
        return {
            **shared_config,
            "TESTING": True,
            "SECRET_KEY": "",
            "DATABASE_URL": "",
            "WTF_CSRF_ENABLED": False,
        }
    else:
        return {
            **shared_config,
            "TESTING": False,
            "SECRET_KEY": os.environ.get("SECRET_FLASK_KEY"),
            "DATABASE_URL": f"postgresql://{os.environ["RDS_USERNAME"]}:{os.environ["RDS_PASSWORD"]}@{os.environ["RDS_HOSTNAME"]}:{os.environ["RDS_PORT"]}/{os.environ["RDS_DB_NAME"]}",
        }
