from scripts.db_overview import build


def test_overview_lists_tables_by_area_and_hides_secrets(app, make_user):
    user = make_user(unit_number="2A", door_code="SECRETCODE1234")
    path, page = build(app)
    assert "users" in page and "access_logs" in page and "Accounts and access" in page
    assert "doors.id" in page and "rows" in page
    assert user.password_hash not in page and "SECRETCODE1234" not in page and "hidden" in page
