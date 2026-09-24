def test_dashboard_scan_and_offline_assets(client):
    for path in ["/", "/scan"]:
        response = client.get(path)
        assert response.status_code == 200
        assert '<html lang="ru">' in response.text
        assert "cdn." not in response.text
    for path in ["app.js", "app.css", "dashboard.js", "scan.js", "vendor/chart.umd.min.js"]:
        assert client.get("/static/" + path).status_code == 200
    assert "vpn.lab.local" in client.get("/api/demo-targets").json()["text"]
