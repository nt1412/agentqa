import json

from typer.testing import CliRunner

from cli import main as cli

runner = CliRunner()


def test_request_builds_url_and_headers(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {"ok": True}

        def raise_for_status(self):
            pass

    def fake_request(method, url, headers=None, json=None, params=None):
        captured.update(method=method, url=url, headers=headers, json=json, params=params)
        return FakeResp()

    monkeypatch.setattr(cli.httpx, "request", fake_request)
    monkeypatch.setenv("AGENTQA_API_URL", "http://x:8000")
    monkeypatch.setenv("AGENTQA_API_KEY", "aqa_test")
    out = cli._request("GET", "/api/v1/projects")
    assert out == {"ok": True}
    assert captured["url"] == "http://x:8000/api/v1/projects"
    assert captured["headers"]["X-API-Key"] == "aqa_test"


def test_project_create_invokes_post(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_request", lambda m, p, **k: calls.append((m, p, k)) or {"id": 1})
    result = runner.invoke(cli.app, ["project", "create", "Demo", "--prefix", "DEMO"])
    assert result.exit_code == 0
    assert calls[0][0] == "POST"
    assert calls[0][1] == "/api/v1/projects"


def test_case_create_from_file(monkeypatch, tmp_path):
    spec = tmp_path / "case.json"
    spec.write_text(json.dumps({"name": "c", "steps": [{"action": "go"}]}))
    calls = []
    monkeypatch.setattr(cli, "_request", lambda m, p, **k: calls.append((m, p, k)) or {"id": 9})
    result = runner.invoke(cli.app, ["case", "create", "5", "--from-file", str(spec)])
    assert result.exit_code == 0
    assert calls[0][2]["json_body"]["name"] == "c"
