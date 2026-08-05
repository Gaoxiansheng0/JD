from fastapi.testclient import TestClient

from resumefit.app import create_app


def test_health_endpoint_reports_ok(tmp_path):
    client = TestClient(create_app(tmp_path))

    assert client.get("/api/health").json() == {"status": "ok"}
