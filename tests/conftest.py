import pytest
from app import create_app
from config import getConfig
from testcontainers.postgres import PostgresContainer
import os
from .test_data import TEST_CV

os.environ["TESTCONTAINERS_RYUK_DISABLED"] = "true"


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine", driver=None) as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def app(postgres_container):
    app = create_app(
        config=getConfig(
            testing=True, testing_overrides={"DATABASE_URL": postgres_container}
        )
    )

    with app.app_context():
        setup_database(app)
        yield app


def setup_database(app):
    """Helper to create tables in the temporary container."""
    from app.db import get_db

    with app.app_context():
        db = get_db()
        with db, db.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS users (id VARCHAR(12) PRIMARY KEY, is_disabled bool, contact_id INT, password_hash text, require_pw_update bool DEFAULT true);"
            )
            cur.execute(
                "CREATE TABLE IF NOT EXISTS cv (id UUID PRIMARY KEY, data_owner VARCHAR(300), date_uploaded TIMESTAMP, pin_code VARCHAR(6), contact_id INT, settings_json json DEFAULT '{}', cv_json json);"
            )
            cur.execute(
                "CREATE TABLE IF NOT EXISTS contact_info (id integer PRIMARY KEY, name VARCHAR(45), email VARCHAR(100), phone VARCHAR(45));"
            )
            cur.execute(
                """
                INSERT INTO users (id, is_disabled, contact_id, password_hash, require_pw_update)
                VALUES ('tester', false, 1, 'pass', false)
                """
            )
            cur.execute(
                f"""
                INSERT INTO cv (id, data_owner, date_uploaded, pin_code, contact_id, settings_json, cv_json)
                VALUES ('{TEST_CV.id}', '{TEST_CV.data_owner}', now(), '{TEST_CV.pin_code}', 1, '{TEST_CV.settings.toJSON()}', '{TEST_CV.cv_data.toJSON()}')
                """
            )
            cur.execute(
                """
                INSERT INTO contact_info(id, name, email, phone)
                VALUES (1, 'Contactee', 'mail@app.com', '+123 45 678 99 10')
                """
            )
            db.commit()


@pytest.fixture(autouse=True)
def clean_db(app, postgres_container):
    import psycopg2

    db = psycopg2.connect(postgres_container)
    db.autocommit = True  # This prevents 'Idle in Transaction' state

    with db.cursor() as cur:
        # Fixes an issue where a test hangs infinitely due to unclosed connections
        cur.execute("SET lock_timeout = '1s';")
        tables = ["users", "cv", "contact_info"]
        cur.execute(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE;")

    db.commit()

    setup_database(app)
    db.close()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def authenticated_user(client):
    """Fake a login"""
    with client.session_transaction() as sess:
        sess["user_id"] = "tester"
    return client


@pytest.fixture
def pin_user(client):
    """Fake a PIN user"""
    with client.session_transaction() as sess:
        sess["pin_code"] = TEST_CV.pin_code
        sess["pin_user"] = TEST_CV.data_owner
    return client
