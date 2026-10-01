def test_resident_page_has_offline_handling(make_user, login, client, main_door):
    login(make_user())
    page = client.get("/simulate").data
    assert b'id="offline-banner"' in page and b"d-none" in page
    assert page.count(b"access-btn") >= 3
    assert b"AbortSignal.timeout(REQUEST_TIMEOUT_MS)" in page and b"setInterval(checkHealth" in page


def test_health_endpoint_available_without_login(client):
    res = client.get("/health")
    assert res.status_code == 200 and res.json["server"] == "healthy"
