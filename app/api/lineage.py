from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.services import lineage

router = APIRouter(prefix="/api/v1", tags=["lineage"])


@router.get("/plans/{plan_id}/build-timeline")
async def build_timeline(plan_id: int, session: SessionDep, user: CurrentUser):
    """Builds for a plan, newest first, each with its pass/fail/blocked/not_run rollup."""
    return await lineage.list_builds_enriched(session, plan_id)


@router.get("/builds/{build_id}")
async def build_detail(build_id: int, session: SessionDep, user: CurrentUser):
    """Build header + rollup + each case's latest result in the build."""
    return await lineage.build_detail(session, build_id)


@router.get("/cases/{case_id}/history")
async def case_history(case_id: int, session: SessionDep, user: CurrentUser):
    """A case's latest result per build, chronological, with broke/fixed transitions."""
    return await lineage.case_history(session, case_id)


@router.get("/builds/{build_id}/compare")
async def compare(build_id: int, session: SessionDep, user: CurrentUser, to: str = "baseline"):
    """Classify each case between this build and another build (?to=<id>) or its
    auto-resolved baseline (?to=baseline): regression / fixed / still_failing /
    still_passing / new_test / removed."""
    return await lineage.compare(session, build_id, to)


@router.get("/projects/{project_id}/branches")
async def branch_status(project_id: int, session: SessionDep, user: CurrentUser):
    """Merge-readiness per active branch: verdict summed across all plans at the
    branch's head commit (BLOCKED if any plan regresses), with per-plan breakdown."""
    return await lineage.branch_status(session, project_id)


@router.get("/projects/{project_id}/case-status")
async def case_status(project_id: int, session: SessionDep, user: CurrentUser):
    """Per-case latest run-status + recent statuses (for the suite browser's inline
    result badge + sparkline). Cases that never ran are absent."""
    return await lineage.case_status_map(session, project_id)


@router.get("/projects/{project_id}/health")
async def project_health(project_id: int, session: SessionDep, user: CurrentUser):
    """Project situational-awareness: latest build per plan, pass-rate trend, flaky
    candidates, open regressions, and re-investigations avoidable (cached fixes)."""
    return await lineage.project_health(session, project_id)


@router.get("/projects/{project_id}/known-regressions")
async def known_regressions(
    project_id: int, session: SessionDep, user: CurrentUser, branch: str | None = None
):
    """Open regressions on active branches, each annotated with its known fix-path
    (broke@→fixed@ + prior reasoning) when one exists — the pre-flight that saves
    re-investigating an already-diagnosed failure."""
    return await lineage.known_regressions(session, project_id, branch)
