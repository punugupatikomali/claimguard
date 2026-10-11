from fastapi.testclient import TestClient
from web.server import app

client = TestClient(app)


def test_home_serves_dashboard():
    response = client.get("/")
    assert response.status_code == 200 and "ClaimGuard" in response.text


def test_scenario_returns_report_and_verdict():
    keys = [s["key"] for s in client.get("/api/scenarios").json()]
    assert "room_cap" in keys
    body = client.get("/api/scenarios/room_cap").json()
    assert body["report"]["potential_exposure"] == 10500
    assert body["verdict"]["recommended_action"] == "HOLD FOR MANUAL REVIEW"
    assert client.get("/api/scenarios/nope").status_code == 404


def test_audit_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    files = {"bill": ("bill.txt", b"x"), "policy": ("policy.txt", b"y")}
    assert client.post("/api/audit", files=files).status_code == 503


def test_audit_rejects_unreadable_document_before_calling_claude(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    files = {"bill": ("bill.docx", b"data"), "policy": ("policy.txt", b"policy text")}
    response = client.post("/api/audit", files=files)
    assert response.status_code == 400 and "PDF" in response.json()["detail"]
