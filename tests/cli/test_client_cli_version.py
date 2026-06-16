import httpx

from app.cli.client import AgentsClient


def test_cli_version_calls_expected_endpoint(monkeypatch):
    requested = {}

    def handler(request: httpx.Request) -> httpx.Response:
        requested["url"] = str(request.url)
        return httpx.Response(200, json={"version": "9.9.9"})

    transport = httpx.MockTransport(handler)
    real_client_cls = httpx.Client  # capture before patching — httpx.Client is one shared module object
    monkeypatch.setattr(
        "app.cli.client.httpx.Client",
        lambda *args, **kwargs: real_client_cls(*args, **{**kwargs, "transport": transport}),
    )

    client = AgentsClient(base_url="https://example.test")
    result = client.cli_version()

    assert result == {"version": "9.9.9"}
    assert requested["url"] == "https://example.test/cli/version"


def test_download_cli_binary_writes_response_bytes(tmp_path, monkeypatch):
    payload = b"fake-binary-bytes"
    requested = {}

    def handler(request: httpx.Request) -> httpx.Response:
        requested["url"] = str(request.url)
        return httpx.Response(200, content=payload)

    transport = httpx.MockTransport(handler)

    def fake_stream(method, url, **kwargs):
        return httpx.Client(transport=transport).stream(method, url, **kwargs)

    monkeypatch.setattr("app.cli.client.httpx.stream", fake_stream)

    client = AgentsClient(base_url="https://example.test")
    dest = tmp_path / "agents-linux"
    client.download_cli_binary(dest, target_os="linux")

    assert dest.read_bytes() == payload
    assert requested["url"] == "https://example.test/cli/download/linux"
