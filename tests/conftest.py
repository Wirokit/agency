import boto3
from moto import mock_aws
import pytest
from app import create_app
from config import getConfig
from testcontainers.postgres import PostgresContainer
import os
from models import AuthType
from app.services.utils import bcrypt
from .test_data import TEST_ADMIN
from yoyo import get_backend, read_migrations

os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"


def setup_database(app):
    """Helper to fill the testing db"""
    from app.db import get_db

    with app.app_context():
        db = get_db()
        with db, db.cursor() as cur:
            query = """
                INSERT INTO users (
                    id,
                    username,
                    is_disabled,
                    password_hash,
                    require_pw_update,
                    full_name,
                    title,
                    office,
                    user_type_id,
                    phone_num,
                    email,
                    pin_code
                ) VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """

            cur.execute(
                query,
                (
                    TEST_ADMIN["id"],
                    TEST_ADMIN["username"],
                    TEST_ADMIN["is_disabled"],
                    bcrypt.generate_password_hash(
                        TEST_ADMIN["unhashed_password"]
                    ).decode("utf-8"),
                    TEST_ADMIN["require_pw_update"],
                    TEST_ADMIN["full_name"],
                    TEST_ADMIN["title"],
                    TEST_ADMIN["office"],
                    TEST_ADMIN["user_type_id"],
                    TEST_ADMIN["phone_num"],
                    TEST_ADMIN["email"],
                    TEST_ADMIN["pin_code"],
                ),
            )
            db.commit()


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine", driver=None) as postgres:
        db_url = postgres.get_connection_url()

        # Configure Yoyo backend with the container's URL
        backend = get_backend(db_url)

        # Read all migration files from the migrations directory
        migrations_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "migrations")
        )
        migrations = read_migrations(migrations_dir)

        # Apply the migrations to the test database
        if len(migrations) > 0:
            with backend.lock():
                backend.apply_migrations(backend.to_apply(migrations))

        yield postgres


@pytest.fixture(scope="session")
def s3_container():
    with mock_aws():
        # Set required dummy env vars
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_DEFAULT_REGION"] = "eu-north-1"

        # Create your bucket
        s3 = boto3.client("s3", region_name="eu-north-1")
        bucket_name = "my-test-bucket"
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={"LocationConstraint": "eu-north-1"},
        )

        yield {"bucket_name": bucket_name}


@pytest.fixture(scope="session")
def app(postgres_container, s3_container):
    app = create_app(
        config=getConfig(
            testing=True,
            testing_overrides={
                "DATABASE_URL": postgres_container.get_connection_url(),
                "S3_PROFILE_IMG_BUCKET": s3_container["bucket_name"],
            },
        )
    )

    with app.app_context():
        setup_database(app)
        yield app


@pytest.fixture(autouse=True)
def clean_db(app):
    import psycopg2

    db = psycopg2.connect(app.config["DATABASE_URL"])
    db.autocommit = True  # This prevents 'Idle in Transaction' state

    with db.cursor() as cur:
        # Fixes an issue where a test hangs infinitely due to unclosed connections
        cur.execute("SET lock_timeout = '1s';")
        tables = [
            "cv",
            "cv_educations",
            "cv_job_experiences",
            "cv_profile_texts",
            "cv_skills",
            "skills",
            "users",
        ]
        cur.execute(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE;")

    db.commit()

    setup_database(app)
    db.close()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_user(client):
    """Fake a login"""
    with client.session_transaction() as sess:
        sess.permanent = True
        sess["user_id"] = TEST_ADMIN["id"]
        sess["user_name"] = TEST_ADMIN["full_name"]
        sess["user_type"] = AuthType.ADMIN.value
        sess["session_version"] = 0
    return client


# @pytest.fixture
# def external_user(client):
#    """Fake a PIN user"""
#    with client.session_transaction() as sess:
#        sess["pin_code"] = TEST_CV.pin_code
#        sess["pin_user"] = TEST_CV.data_owner
#    return client
