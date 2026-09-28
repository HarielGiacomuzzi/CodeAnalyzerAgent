from pathlib import Path

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_root_serves_the_ui():
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    for element_id in ['id="code"', 'id="file"', 'id="language"', 'id="analysis-type"', 'id="analyze-btn"', 'id="results"']:
        assert element_id in r.text


def test_assets_are_served_and_api_still_wins():
    assert client.get("/app.js").status_code == 200
    assert client.get("/styles.css").status_code == 200
    assert client.get("/health").json()["status"] == "ok"


def test_app_js_never_injects_html():
    assert "innerHTML" not in Path("static/app.js").read_text()
