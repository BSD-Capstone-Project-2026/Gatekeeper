def test_menu_lists_demo_accounts_in_development(make_user, login, client):
    me = make_user(email="aisha.khan@gatekeeper.demo")
    make_user("concierge", email="priya.sharma@gatekeeper.demo")
    make_user("management", email="real.manager@building.local")
    login(me)
    page = client.get("/dashboard").data.decode()
    assert "Switch demo account" in page and "concierge" in page.lower()
    assert "real.manager" not in page


def test_switch_to_demo_account(make_user, login, client):
    login(make_user(email="aisha.khan@gatekeeper.demo"))
    priya = make_user("concierge", email="priya.sharma@gatekeeper.demo")
    assert client.post(f"/dev/switch-account/{priya.id}").location.endswith("/dashboard")
    with client.session_transaction() as sess:
        assert sess["user_id"] == priya.id and sess["user_role"] == "concierge"


def test_cannot_switch_to_non_demo_account(make_user, login, client):
    login(make_user(email="aisha.khan@gatekeeper.demo"))
    boss = make_user("management", email="boss@building.local")
    assert client.post(f"/dev/switch-account/{boss.id}").status_code == 403


def test_switching_disabled_outside_development(app, make_user, login, client):
    app.config["APP_ENV"] = "production"
    login(make_user(email="aisha.khan@gatekeeper.demo"))
    priya = make_user("concierge", email="priya.sharma@gatekeeper.demo")
    assert "Switch demo account" not in client.get("/profile").data.decode()
    assert client.post(f"/dev/switch-account/{priya.id}").status_code == 403
