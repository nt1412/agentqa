"""AgentQA MCP server.

Tools wrap the service layer directly. Each tool opens its own DB session.
Phase 1 implements the 6 entity-backed tools; the rest are registered as
explicit stubs raising NotImplementedError until their phase lands.
"""

from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from app.db import SessionLocal
from app.schemas.execution import ExecutionCreate, StepResultIn
from app.schemas.testcase import StepIn, TestCaseCreate
from app.services import assignments, executions, suites, testcases

mcp = FastMCP("agentqa")


@asynccontextmanager
async def _session():
    async with SessionLocal() as s:
        yield s


def _version_dump(out) -> dict | None:
    if out.current_version is None:
        return None
    cv = out.current_version
    return {
        "version": cv.version,
        "summary": cv.summary,
        "preconditions": cv.preconditions,
        "importance": cv.importance,
        "execution_type": cv.execution_type,
        "status": cv.status,
        "steps": [
            {
                "step_number": s.step_number,
                "action": s.action,
                "expected_result": s.expected_result,
            }
            for s in cv.steps
        ],
    }


def _case_dump(out) -> dict:
    return {
        "id": out.id,
        "external_id": out.external_id,
        "name": out.name,
        "suite_id": out.suite_id,
        "project_id": out.project_id,
        "current_version": _version_dump(out),
    }


# ---------- Phase 1: entity-backed tools ----------


@mcp.tool()
async def create_test_suite(project_id: int, path: str, details: str | None = None) -> dict:
    """Find-or-create a test suite by slash-delimited path, e.g. 'Auth/Login/OAuth'."""
    async with _session() as s:
        suite = await suites.find_or_create_path(s, project_id, path)
        return {"id": suite.id, "name": suite.name, "parent_id": suite.parent_id}


@mcp.tool()
async def create_test_case(
    project_id: int,
    suite_path: str,
    name: str,
    summary: str | None = None,
    preconditions: str | None = None,
    steps: list[dict] | None = None,
    importance: int = 2,
    execution_type: str = "manual",
) -> dict:
    """Create a full test case (with version 1 + steps) under a suite path."""
    async with _session() as s:
        suite = await suites.find_or_create_path(s, project_id, suite_path)
        tc = await testcases.create_test_case(
            s,
            suite.id,
            TestCaseCreate(
                name=name,
                summary=summary,
                preconditions=preconditions,
                importance=importance,
                execution_type=execution_type,
                steps=[StepIn(**st) for st in (steps or [])],
            ),
        )
        out = await testcases.get_test_case(s, tc.id)
        return _case_dump(out)


@mcp.tool()
async def bulk_create_test_cases(project_id: int, suite_path: str, cases: list[dict]) -> list[dict]:
    """Create many test cases under one suite path in a single call."""
    async with _session() as s:
        suite = await suites.find_or_create_path(s, project_id, suite_path)
        created = []
        for c in cases:
            tc = await testcases.create_test_case(
                s,
                suite.id,
                TestCaseCreate(
                    name=c["name"],
                    summary=c.get("summary"),
                    preconditions=c.get("preconditions"),
                    importance=c.get("importance", 2),
                    execution_type=c.get("execution_type", "manual"),
                    steps=[StepIn(**st) for st in c.get("steps", [])],
                ),
            )
            out = await testcases.get_test_case(s, tc.id)
            created.append(_case_dump(out))
        return created


@mcp.tool()
async def get_test_case(
    case_id: int | None = None,
    external_id: str | None = None,
    project_id: int | None = None,
) -> dict:
    """Fetch a test case (current version + steps) by id, or external_id + project_id."""
    async with _session() as s:
        if case_id is not None:
            out = await testcases.get_test_case(s, case_id)
        elif external_id is not None and project_id is not None:
            out = await testcases.get_by_external_id(s, project_id, external_id)
        else:
            raise ValueError("provide case_id, or external_id + project_id")
        return _case_dump(out)


@mcp.tool()
async def search_test_cases(project_id: int, query: str) -> list[dict]:
    """Search test cases by name substring — call before creating duplicates."""
    async with _session() as s:
        rows = await testcases.search_test_cases(s, project_id, query)
        return [{"id": r.id, "external_id": r.external_id, "name": r.name} for r in rows]


@mcp.tool()
async def record_test_run(
    case_id: int,
    plan_id: int,
    build_name: str,
    status: str,
    commit_id: str | None = None,
    step_results: list[dict] | None = None,
    notes: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Record an execution result. Build is upserted by (plan, build_name)."""
    async with _session() as s:
        ex = await executions.record_execution(
            s,
            ExecutionCreate(
                case_id=case_id,
                plan_id=plan_id,
                build_name=build_name,
                commit_id=commit_id,
                status=status,
                step_results=[StepResultIn(**sr) for sr in (step_results or [])],
                notes=notes,
                session_id=session_id,
            ),
            tester_id=None,  # MCP callers are agents
        )
        return {
            "id": ex.id,
            "status": ex.status,
            "build_id": ex.build_id,
            "version_id": ex.version_id,
        }


@mcp.tool()
async def assign_test(
    case_id: int,
    plan_id: int,
    assignee_id: int,
    assignee_type: str,
    deadline: str | None = None,
) -> dict:
    """Assign a test case (in a plan) to a human or agent. assignee_type: human|agent."""
    import datetime as _dt

    parsed_deadline = _dt.datetime.fromisoformat(deadline) if deadline else None
    async with _session() as s:
        from app.schemas.assignment import AssignmentCreate

        a = await assignments.create_assignment(
            s,
            AssignmentCreate(
                case_id=case_id,
                plan_id=plan_id,
                assignee_id=assignee_id,
                assignee_type=assignee_type,
                deadline=parsed_deadline,
            ),
            assigner_id=None,  # MCP callers are agents; no human assigner
        )
        return {"id": a.id, "status": a.status, "assignee_id": a.assignee_id}


@mcp.tool()
async def list_assignments(
    plan_id: int | None = None,
    assignee_id: int | None = None,
    status: str | None = None,
) -> list[dict]:
    """List assignments, optionally filtered — agents poll this to discover work."""
    async with _session() as s:
        rows = await assignments.list_assignments(s, plan_id, assignee_id, status)
        return [
            {
                "id": a.id,
                "case_id": a.case_id,
                "plan_id": a.plan_id,
                "assignee_id": a.assignee_id,
                "assignee_type": a.assignee_type,
                "status": a.status,
            }
            for a in rows
        ]


# ---------- Deferred tools (registered, bodies land in later phases) ----------

_DEFERRED = [
    "get_failure_context",
    "search_similar_failures",
    "get_agent_execution_history",
    "get_execution_evidence",
    "list_unverified_claims",
    "verify_claim",
    "evaluate_test_case",
    "create_audit_report",
    "get_coverage_gaps",
    "create_requirement",
    "upload_artifact",
]


def _make_stub(tool_name: str):
    @mcp.tool(name=tool_name)
    async def _stub(**kwargs) -> dict:
        raise NotImplementedError(f"{tool_name} is implemented in a later phase")

    return _stub


for _name in _DEFERRED:
    _make_stub(_name)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
