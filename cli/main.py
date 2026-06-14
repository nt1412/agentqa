import json
import os
from pathlib import Path

import httpx
import typer

app = typer.Typer(help="AgentQA CLI")
project_app = typer.Typer(help="Manage projects")
suite_app = typer.Typer(help="Manage suites")
case_app = typer.Typer(help="Manage test cases")
run_app = typer.Typer(help="Record/inspect executions")
app.add_typer(project_app, name="project")
app.add_typer(suite_app, name="suite")
app.add_typer(case_app, name="case")
app.add_typer(run_app, name="run")


def _request(method: str, path: str, *, json_body=None, params=None) -> dict:
    base = os.environ.get("AGENTQA_API_URL", "http://localhost:8000")
    headers = {}
    api_key = os.environ.get("AGENTQA_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    resp = httpx.request(method, base + path, headers=headers, json=json_body, params=params)
    resp.raise_for_status()
    return resp.json()


def _print(data) -> None:
    typer.echo(json.dumps(data, indent=2, default=str))


@project_app.command("list")
def project_list():
    _print(_request("GET", "/api/v1/projects"))


@project_app.command("create")
def project_create(name: str, prefix: str = typer.Option(..., "--prefix")):
    _print(_request("POST", "/api/v1/projects", json_body={"name": name, "prefix": prefix}))


@project_app.command("get")
def project_get(project_id: int):
    _print(_request("GET", f"/api/v1/projects/{project_id}"))


@suite_app.command("create")
def suite_create(
    project_id: int,
    name: str = typer.Option(..., "--name"),
    parent: int | None = typer.Option(None, "--parent"),
):
    _print(
        _request(
            "POST",
            f"/api/v1/projects/{project_id}/suites",
            json_body={"name": name, "parent_id": parent},
        )
    )


@suite_app.command("tree")
def suite_tree(suite_id: int):
    _print(_request("GET", f"/api/v1/suites/{suite_id}/tree"))


@case_app.command("create")
def case_create(
    suite_id: int,
    name: str = typer.Option(None, "--name"),
    from_file: Path = typer.Option(None, "--from-file"),  # noqa: B008
):
    if from_file:
        body = json.loads(from_file.read_text())
    elif name:
        body = {"name": name}
    else:
        raise typer.BadParameter("provide --name or --from-file")
    _print(_request("POST", f"/api/v1/suites/{suite_id}/cases", json_body=body))


@case_app.command("get")
def case_get(case_id: int):
    _print(_request("GET", f"/api/v1/cases/{case_id}"))


@run_app.command("record")
def run_record(
    case_id: int,
    plan: int = typer.Option(..., "--plan"),
    build: str = typer.Option(..., "--build"),
    status: str = typer.Option(..., "--status"),
    from_file: Path = typer.Option(None, "--steps-file"),  # noqa: B008
    notes: str = typer.Option(None, "--notes"),
):
    body = {"case_id": case_id, "plan_id": plan, "build_name": build, "status": status}
    if from_file:
        body["step_results"] = json.loads(from_file.read_text())
    if notes:
        body["notes"] = notes
    _print(_request("POST", "/api/v1/executions", json_body=body))


@run_app.command("list")
def run_list(case: int = typer.Option(..., "--case")):
    _print(_request("GET", f"/api/v1/cases/{case}/executions"))


if __name__ == "__main__":
    app()
