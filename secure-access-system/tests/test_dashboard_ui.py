from models import db, Incident


def test_staff_dashboard_cards(make_user, login, client):
    db.session.add(Incident(unit_number="3B", status="open", attempt_count=3))
    db.session.commit()
    login(make_user("management"))
    page = client.get("/dashboard").data.decode()
    assert page.count("stat-card") == 4
    for title in ["System Health", "Open Incidents", "Recent Activity", "Users by Role", "Recent Users"]:
        assert title in page
    assert "Unit 3B · 3 failed attempts" in page and "Quick Actions" not in page


def test_resident_dashboard_offers_access(make_user, login, client):
    login(make_user())
    page = client.get("/dashboard").data.decode()
    assert "Open Access" in page and "stat-card" not in page and "Open Incidents" not in page


def test_sidebar_sections_slide_and_remember(make_user, login, client):
    login(make_user("management"))
    page = client.get("/dashboard").data.decode()
    assert page.count('data-bs-toggle="collapse"') == 5 and "localStorage.setItem(key, 'closed')" in page


def test_account_menu_has_profile_password_and_sign_out(make_user, login, client):
    login(make_user())
    page = client.get("/dashboard").data.decode()
    menu = page[page.index('class="dropdown-menu"'):page.index("</ul>", page.index('class="dropdown-menu"'))]
    assert "Profile" in menu and "Change Password" in menu and "Sign Out" in menu


def test_stats_include_every_role(make_user, login, client):
    make_user("guest")
    make_user("cleaner")
    login(make_user("management"))
    counts = client.get("/api/dashboard/stats").json["role_counts"]
    assert counts == {"guest": 1, "cleaner": 1, "management": 1}


def test_menu_and_card_styles(client):
    css = client.get("/static/css/app.css").data
    assert b"@keyframes menu-in" in css and b".stat-card" in css and b".app-nav-group.collapsing" in css
