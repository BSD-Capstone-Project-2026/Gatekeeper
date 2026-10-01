import pytest


def test_login_has_no_prefilled_credentials(client):
    page = client.get("/login").data
    assert b'value="demo@building.local"' not in page and b'value="DemoPass123"' not in page
    assert b"Sign in to Gatekeeper" in page and b"Forgot password?" in page and b"auth-card" in page


def test_demo_hint_only_in_development(app, client):
    assert b"Development demo account" in client.get("/login").data
    app.config["APP_ENV"] = "production"
    assert b"Development demo account" not in client.get("/login").data


def test_failed_login_keeps_email(client, make_user):
    user = make_user()
    page = client.post("/login", data={"email": user.email, "password": "wrong"}).data
    assert f'value="{user.email}"'.encode() in page and b"Invalid credentials" in page


@pytest.mark.parametrize("path", ["/forgot-password", "/reset-password/unknown-token"])
def test_password_pages_use_card_layout(client, path):
    assert b"auth-card" in client.get(path).data


def test_change_password_requires_eight_characters(make_user, login, client):
    user = make_user()
    login(user)
    page = client.post("/reset-password", data={"current_password": "Passw0rd!", "new_password": "short7!", "confirm_password": "short7!"}).data
    assert b"at least 8 characters" in page and b'class="app-nav"' in page


def test_profile_groups_account_and_notifications(make_user, login, client):
    login(make_user())
    page = client.get("/profile").data
    assert b'class="app-nav"' in page and b">Account<" in page and b"Security Notifications" in page
    assert b'href="#"' not in page


def test_error_page_is_plain(make_user, login, client):
    login(make_user())
    page = client.get("/doors").data
    assert b"Unable to continue" in page and b"Back to Dashboard" in page
