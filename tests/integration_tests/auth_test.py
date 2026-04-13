def test_unauthorized_access(client):
    # All access should redirect to the login page
    response = client.get("/")
    assert response.status_code == 302

    # Fetching list of all CVs should not be allowed
    response = client.get("/api/cv")
    assert response.status_code == 401


def test_admin_access(authenticated_user):
    # Access should not redirect
    response = authenticated_user.get("/")
    assert response.status_code == 200

    # Should be able to fetch a list of all CVs
    response = authenticated_user.get("/api/cv")
    assert response.status_code == 200


def test_pin_user_access(pin_user):
    # Access should not redirect
    response = pin_user.get("/")
    assert response.status_code == 200

    # Fetching list of all CVs should not be allowed
    response = pin_user.get("/api/cv")
    assert response.status_code == 401
