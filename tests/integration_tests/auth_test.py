import json
from datetime import timedelta
from uuid import uuid4
import pytest
from app.db import get_db
from app.services.utils import bcrypt
from models import AuthType
from tests.test_data import TEST_ADMIN


@pytest.fixture
def query_db(app):
    def execute(query, params=()):
        with app.app_context():
            db = get_db()
            with db, db.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall() if cur.description else None

    return execute


@pytest.fixture
def logged_in_admin(app, client, query_db):
    password = TEST_ADMIN["unhashed_password"]
    with app.app_context():
        password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
    query_db(
        "UPDATE users SET password_hash = %s WHERE id = %s",
        (password_hash, TEST_ADMIN["id"]),
    )
    response = client.post(
        "/auth/login", data={"user": TEST_ADMIN["username"], "password": password}
    )
    assert response.status_code == 200
    assert response.get_json()["success"] is True
    with client.session_transaction() as sess:
        assert sess.permanent is True
    return client


@pytest.fixture
def logged_in_external(client, query_db):
    user_id = uuid4()
    pin = "123456"
    query_db(
        """
        INSERT INTO users (id, full_name, user_type_id, pin_code)
        VALUES (%s, %s, 3, %s)
        """,
        (user_id, "External Regression User", pin),
    )
    response = client.post("/auth/pin-login", data={"pin": pin})
    assert response.status_code == 200
    assert response.get_json()["success"] is True
    with client.session_transaction() as sess:
        assert sess.permanent is True
    return client, user_id, pin


def assert_logged_out(client):
    with client.session_transaction() as sess:
        assert "user_id" not in sess
        assert "user_type" not in sess
        assert "user_name" not in sess


def test_permanent_session_lifetime_is_24_hours(app):
    assert app.config["PERMANENT_SESSION_LIFETIME"] == timedelta(hours=24)


def test_unauthorized_access(client):
    # All view access should redirect to the login page
    response = client.get("/")
    assert response.status_code == 302

    # API access should be restricted
    response = client.delete("/api/profile/daae7e07-173a-4849-a6ba-5932ab43d942")
    assert response.status_code == 401


def test_non_permanent_authenticated_session_is_cleared(client):
    with client.session_transaction() as sess:
        sess["user_id"] = TEST_ADMIN["id"]
        sess["user_type"] = AuthType.ADMIN.value
        sess["user_name"] = TEST_ADMIN["full_name"]

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"
    assert_logged_out(client)


def test_admin_access(admin_user):
    # View access should not redirect
    response = admin_user.get("/")
    assert response.status_code == 200

    # API access should NOT be restricted
    response = admin_user.delete("/api/profile/daae7e07-173a-4849-a6ba-5932ab43d942")
    assert response.status_code == 200


def test_demoted_admin_cannot_edit_another_users_targeted_cv(logged_in_admin, query_db):
    owner_id = uuid4()
    cv_id = uuid4()
    query_db(
        "INSERT INTO users (id, full_name, user_type_id) VALUES (%s, %s, 3)",
        (owner_id, "Other Candidate"),
    )
    query_db(
        """
        INSERT INTO cv (id, owner_id, name, title, is_source)
        VALUES (%s, %s, %s, %s, false)
        """,
        (cv_id, owner_id, "Original Name", "Original Title"),
    )
    query_db("UPDATE users SET user_type_id = 2 WHERE id = %s", (TEST_ADMIN["id"],))

    response = logged_in_admin.patch(
        f"/api/cv/{cv_id}",
        data={
            "cv_json": json.dumps({"name": "Unauthorized Edit", "title": "Changed"}),
            "contact_id": "",
        },
    )

    assert response.status_code == 401
    assert_logged_out(logged_in_admin)
    assert query_db("SELECT name, title FROM cv WHERE id = %s", (cv_id,)) == [
        {"name": "Original Name", "title": "Original Title"}
    ]


@pytest.mark.parametrize("path", ["/", "/login"])
def test_demoted_admin_page_redirects_to_login(logged_in_admin, query_db, path):
    query_db("UPDATE users SET user_type_id = 2 WHERE id = %s", (TEST_ADMIN["id"],))

    response = logged_in_admin.get(path)

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"
    assert_logged_out(logged_in_admin)
    login_response = logged_in_admin.get("/login")
    assert login_response.status_code == 200


@pytest.mark.parametrize("new_role_id", [1, 2])
def test_promoted_external_session_is_rejected(
    logged_in_external, query_db, new_role_id
):
    client, user_id, _ = logged_in_external
    query_db(
        "UPDATE users SET user_type_id = %s WHERE id = %s",
        (new_role_id, user_id),
    )

    response = client.patch(f"/api/profile/{user_id}", data={})

    assert response.status_code == 401
    assert_logged_out(client)


@pytest.mark.parametrize("new_role_id", [1, 2])
def test_promoted_external_cannot_log_in_with_old_pin(
    logged_in_external, query_db, new_role_id
):
    client, user_id, pin = logged_in_external
    query_db(
        "UPDATE users SET user_type_id = %s WHERE id = %s",
        (new_role_id, user_id),
    )
    assert client.post("/auth/logout").get_json()["success"] is True

    response = client.post("/auth/pin-login", data={"pin": pin})

    assert response.get_json()["success"] is False
    assert_logged_out(client)


def test_disabled_external_cannot_log_in_with_pin(logged_in_external, query_db):
    client, user_id, pin = logged_in_external
    query_db("UPDATE users SET is_disabled = true WHERE id = %s", (user_id,))
    assert client.post("/auth/logout").get_json()["success"] is True

    response = client.post("/auth/pin-login", data={"pin": pin})

    assert response.status_code == 404
    assert response.get_json() == {"success": False, "error": "Invalid PIN."}
    assert_logged_out(client)


@pytest.mark.parametrize("account_state", ["disabled", "deleted"])
@pytest.mark.parametrize(
    "path", ["/api/profile/{user_id}", "/api/targeted-cv/{user_id}"]
)
def test_invalid_account_api_rejects_and_clears_session(
    logged_in_admin, query_db, account_state, path
):
    if account_state == "disabled":
        query_db(
            "UPDATE users SET is_disabled = true WHERE id = %s",
            (TEST_ADMIN["id"],),
        )
    else:
        query_db("DELETE FROM users WHERE id = %s", (TEST_ADMIN["id"],))

    response = logged_in_admin.delete(path.format(user_id=TEST_ADMIN["id"]))

    assert response.status_code == 401
    assert_logged_out(logged_in_admin)


@pytest.mark.parametrize("account_state", ["disabled", "deleted"])
def test_invalid_account_page_redirects_to_login(
    logged_in_admin, query_db, account_state
):
    if account_state == "disabled":
        query_db(
            "UPDATE users SET is_disabled = true WHERE id = %s",
            (TEST_ADMIN["id"],),
        )
    else:
        query_db("DELETE FROM users WHERE id = %s", (TEST_ADMIN["id"],))

    response = logged_in_admin.get("/")

    assert response.status_code == 302
    assert response.headers["Location"] == "/login"
    assert_logged_out(logged_in_admin)


def test_unchanged_admin_session_retains_access(logged_in_admin):
    assert logged_in_admin.get("/").status_code == 200
    assert logged_in_admin.get("/change-password").status_code == 200
    with logged_in_admin.session_transaction() as sess:
        assert str(sess["user_id"]) == TEST_ADMIN["id"]
        assert sess["user_type"] == AuthType.ADMIN.value


def test_external_permission_denial_preserves_valid_session(logged_in_external):
    client, user_id, _ = logged_in_external

    response = client.delete(f"/api/targeted-cv/{uuid4()}")

    assert response.status_code == 401
    with client.session_transaction() as sess:
        assert str(sess["user_id"]) == str(user_id)
        assert sess["user_type"] == AuthType.EXTERNAL.value
    assert client.get("/").status_code == 200


def csrf_headers(client):
    assert client.get("/change-password").status_code == 200
    with client.session_transaction() as sess:
        return {"X-CSRF-Token": sess["csrf_token"]}


@pytest.mark.parametrize("token", [None, "wrong-token", "\u00e4"])
def test_password_change_requires_csrf(logged_in_admin, query_db, token):
    data = {
        "old_password": TEST_ADMIN["unhashed_password"],
        "new_password": "Permanent-password-456",
    }

    if token is not None:
        data["csrf_token"] = token

    response = logged_in_admin.open("/auth/password", method="UPDATE", data=data)
    assert response.status_code == 403
    assert (
        query_db(
            "SELECT session_version FROM users WHERE id = %s", (TEST_ADMIN["id"],)
        )[0]["session_version"]
        == 0
    )


@pytest.mark.parametrize(
    "password", ["short", "a" * 65, "\u00e4" * 40, TEST_ADMIN["unhashed_password"]]
)
def test_password_policy_enforced_server_side(logged_in_admin, password):
    response = logged_in_admin.open(
        "/auth/password",
        method="UPDATE",
        headers=csrf_headers(logged_in_admin),
        data={
            "old_password": TEST_ADMIN["unhashed_password"],
            "new_password": password,
        },
    )
    assert response.status_code == 400


def test_password_change_cannot_overwrite_concurrent_session_version_change(
    logged_in_admin, query_db, monkeypatch
):
    headers = csrf_headers(logged_in_admin)
    generate = bcrypt.generate_password_hash

    def concurrent_version_change(password):
        hashed = generate(password)
        query_db(
            "UPDATE users SET session_version = session_version + 1 WHERE id = %s",
            (TEST_ADMIN["id"],),
        )
        return hashed

    monkeypatch.setattr(bcrypt, "generate_password_hash", concurrent_version_change)
    response = logged_in_admin.open(
        "/auth/password",
        method="UPDATE",
        headers=headers,
        data={
            "old_password": TEST_ADMIN["unhashed_password"],
            "new_password": "Permanent-password-456",
        },
    )
    assert response.status_code == 401
    assert_logged_out(logged_in_admin)
    assert bcrypt.check_password_hash(
        query_db("SELECT password_hash FROM users WHERE id = %s", (TEST_ADMIN["id"],))[
            0
        ]["password_hash"],
        TEST_ADMIN["unhashed_password"],
    )


@pytest.mark.parametrize("secret", [None, "", "a" * 31])
def test_production_rejects_missing_or_short_secret(secret):
    from app import create_app
    from config import getConfig

    with pytest.raises(ValueError, match="SECRET_FLASK_KEY"):
        create_app(
            getConfig(
                testing=True,
                testing_overrides={
                    "TESTING": False,
                    "SECRET_KEY": secret,
                },
            )
        )


def test_production_cookie_security(monkeypatch):
    from config import getConfig

    for name in (
        "RDS_USERNAME",
        "RDS_PASSWORD",
        "RDS_HOSTNAME",
        "RDS_PORT",
        "RDS_DB_NAME",
    ):
        monkeypatch.setenv(name, "testing")

    config = getConfig()
    assert config["SESSION_COOKIE_SECURE"] is True
    assert config["SESSION_COOKIE_HTTPONLY"] is True
    assert config["SESSION_COOKIE_SAMESITE"] == "Lax"


def test_legacy_permanent_session_is_revoked(admin_user):
    with admin_user.session_transaction() as sess:
        sess.pop("session_version")

    assert admin_user.delete(f"/api/profile/{TEST_ADMIN['id']}").status_code == 401
    assert_logged_out(admin_user)


def test_disabled_password_account_cannot_login(client, logged_in_admin, query_db):
    query_db("UPDATE users SET is_disabled = true WHERE id = %s", (TEST_ADMIN["id"],))
    assert client.post("/auth/logout").get_json()["success"]
    response = client.post(
        "/auth/login",
        data={
            "user": TEST_ADMIN["username"],
            "password": TEST_ADMIN["unhashed_password"],
        },
    )
    assert not response.get_json()["success"]
    assert_logged_out(client)
