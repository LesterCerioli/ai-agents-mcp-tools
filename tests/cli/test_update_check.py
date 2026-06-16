import json
import time

from app.cli import commands as cli_commands


def test_parse_version_basic():
    assert cli_commands._parse_version("1.2.3") == (1, 2, 3)


def test_parse_version_invalid_falls_back_to_zero():
    assert cli_commands._parse_version("not-a-version") == (0,)


def test_is_newer():
    assert cli_commands._is_newer("0.3.0", "0.2.0") is True
    assert cli_commands._is_newer("0.2.0", "0.2.0") is False
    assert cli_commands._is_newer("0.1.0", "0.2.0") is False


def test_latest_known_version_uses_fresh_cache_without_hitting_network(tmp_path, monkeypatch):
    cache_file = tmp_path / "update_check.json"
    cache_file.write_text(json.dumps({"checked_at": time.time(), "latest_version": "9.9.9"}))
    monkeypatch.setattr(cli_commands, "_UPDATE_CHECK_FILE", cache_file)

    def boom(*args, **kwargs):
        raise AssertionError("should not hit the network when the cache is fresh")

    monkeypatch.setattr(cli_commands, "AgentsClient", boom)

    assert cli_commands._latest_known_version() == "9.9.9"


def test_latest_known_version_refetches_when_cache_expired(tmp_path, monkeypatch):
    cache_file = tmp_path / "update_check.json"
    cache_file.write_text(json.dumps({"checked_at": 0, "latest_version": "0.0.1"}))
    monkeypatch.setattr(cli_commands, "_UPDATE_CHECK_FILE", cache_file)

    class FakeClient:
        def __init__(self, base_url=None):
            pass

        def cli_version(self):
            return {"version": "5.0.0"}

    monkeypatch.setattr(cli_commands, "AgentsClient", FakeClient)

    assert cli_commands._latest_known_version() == "5.0.0"
    assert json.loads(cache_file.read_text())["latest_version"] == "5.0.0"


def test_latest_known_version_silently_returns_none_on_failure(tmp_path, monkeypatch):
    cache_file = tmp_path / "update_check.json"
    monkeypatch.setattr(cli_commands, "_UPDATE_CHECK_FILE", cache_file)

    class FailingClient:
        def __init__(self, base_url=None):
            pass

        def cli_version(self):
            raise RuntimeError("network down")

    monkeypatch.setattr(cli_commands, "AgentsClient", FailingClient)

    assert cli_commands._latest_known_version() is None
    assert not cache_file.exists()
