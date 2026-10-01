import re
import pytest


def test_stylesheet_served_with_light_and_dark_tokens(client):
    css = client.get("/static/css/app.css").data
    assert b'[data-bs-theme="dark"]' in css and b"-apple-system" in css and b"backdrop-filter" in css


def test_every_page_loads_theme_and_stylesheet(client):
    page = client.get("/login").data
    assert b"prefers-color-scheme: dark" in page and b"data-bs-theme" in page
    assert b"bootstrap@5.3" in page and b"css/app.css" in page
    assert b"<style>" not in page


@pytest.mark.parametrize("path", ["/dashboard", "/users", "/create-user", "/incidents", "/profile", "/reset-password", "/zones", "/audit"])
def test_staff_pages_share_one_sidebar(make_user, login, client, path):
    login(make_user("management"))
    page = client.get(path).data.decode()
    assert page.count('class="app-nav"') == 1
    assert len(re.findall(r'app-nav-link active', page)) == 1


def test_sidebar_links_follow_role(make_user, login, client):
    login(make_user())
    page = client.get("/dashboard").data
    assert b"Access History" in page and b"Access</a>" in page
    assert b"Users</a>" not in page and b"Audit Log" not in page
