from fastapi.testclient import TestClient

from app.cli._version import CLI_VERSION
from app.main import app

client = TestClient(app)


def test_cli_version_endpoint_returns_current_version():
    response = client.get("/cli/version")
    assert response.status_code == 200
    assert response.json() == {"version": CLI_VERSION}
