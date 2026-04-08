import pytest
from app import create_app
from config import getConfig


@pytest.fixture(scope="session")
def app():
    app = create_app(config=getConfig(testing=True))

    with app.app_context():
        yield app


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
        sess["pin_code"] = "012345"
    return client
