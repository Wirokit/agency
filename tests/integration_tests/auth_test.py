def test_unauthorized_access(client):
    # All view access should redirect to the login page
    response = client.get("/")
    assert response.status_code == 302

    # API access should be restricted
    response = client.delete("/api/profile/daae7e07-173a-4849-a6ba-5932ab43d942")
    assert response.status_code == 401


def test_admin_access(admin_user):
    # View access should not redirect
    response = admin_user.get("/")
    assert response.status_code == 200

    # API access should NOT be restricted
    response = admin_user.delete("/api/profile/daae7e07-173a-4849-a6ba-5932ab43d942")
    assert response.status_code == 200


""" def test_pin_user_access(pin_user):
    # Access should not redirect
    response = pin_user.get("/")
    assert response.status_code == 200

    # Fetching list of all CVs should not be allowed
    response = pin_user.get("/api/cv")
    assert response.status_code == 401 """
