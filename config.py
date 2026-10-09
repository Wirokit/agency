import os
from datetime import timedelta

# --- Environment - Only needed when running locally ---
""" from dotenv import load_dotenv

load_dotenv() """
# ---


def getConfig(testing=False, testing_overrides={}):
    shared_config = {
        "MAX_CONTENT_LENGTH": 50 * 1024 * 1024,  # Set a max file size (e.g., 50MB)
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
    }

    if testing:
        return {
            **shared_config,
            "TESTING": True,
            "SECRET_KEY": "123456789abcdefg",  # For testing only
            "DATABASE_URL": "",
            "WTF_CSRF_ENABLED": False,
            "BEDROCK_AI_MODEL": "",
            "PERMANENT_SESSION_LIFETIME": timedelta(hours=24),
            "SESSION_COOKIE_SECURE": False,
            **testing_overrides,
        }
    else:
        return {
            **shared_config,
            "TESTING": False,
            "SECRET_KEY": os.environ.get("SECRET_FLASK_KEY"),
            "SESSION_COOKIE_SECURE": True,
            "DATABASE_URL": f"postgresql://{os.environ['RDS_USERNAME']}:{os.environ['RDS_PASSWORD']}@{os.environ['RDS_HOSTNAME']}:{os.environ['RDS_PORT']}/{os.environ['RDS_DB_NAME']}",
            "AWS_S3_ENDPOINT_URL": "https://s3.eu-north-1.amazonaws.com",
            "S3_PROFILE_IMG_BUCKET": os.environ.get("S3_PROFILE_IMG_BUCKET"),
            "BEDROCK_AI_MODEL": os.environ.get("BEDROCK_AI_MODEL"),
            "PERMANENT_SESSION_LIFETIME": timedelta(
                hours=int(os.environ.get("SESSION_DURATION_HOURS", 12))
            ),
        }
