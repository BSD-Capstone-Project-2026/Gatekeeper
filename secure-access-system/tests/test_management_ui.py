import re
import pytest
from models import db, Zone

PAGES = ["/users", "/incidents", "/incident-list", "/audit", "/zones", "/zones/create", "/doors", "/door-controls", "/emergency-override"]


@pytest.mark.parametrize("path", PAGES)
def test_pages_share_header_and_theme_safe_styles(make_user, login, client, path):
    login(make_user("management"))
    page = client.get(path).data.decode()
    assert 'class="page-header"' in page and re.search(r'<p class="text-muted mb-0">\S', page)
    assert "table-dark" not in page and "bg-light" not in page
    assert not re.search("[\U0001F300-\U0001FAFF✅❌]", page)


def test_user_rows_have_action_menu_for_management(make_user, login, client):
    target = make_user(email="target@test.local")
    login(make_user("management"))
    page = client.get("/users").data.decode()
    assert f'aria-label="Actions for {target.username}"' in page and "Manage Zones" in page and "Deactivate" in page


def test_concierge_gets_no_row_actions(make_user, login, client):
    make_user(email="res@test.local")
    login(make_user("concierge"))
    assert "bi-three-dots" not in client.get("/users").data.decode()


def test_zone_menu_offers_edit_and_delete(make_user, login, client):
    db.session.add(Zone(name="Lobby", description="Front"))
    db.session.commit()
    login(make_user("management"))
    page = client.get("/zones").data.decode()
    assert "Edit</a>" in page and 'dropdown-item text-danger"><i class="bi bi-trash"></i>Delete' in page


def test_menu_button_styles(client):
    css = client.get("/static/css/app.css").data
    assert b".btn-icon" in css and b".page-header" in css
