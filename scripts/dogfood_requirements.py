"""Backfill AgentQA's own requirements, coverage, and run-plan hierarchy into
the AQA dogfood project — so the platform fully tracks its own development.

Complements scripts/dogfood.py (which catalogs the pytest suite + records runs).
This adds the layers that close the loop into "full use":

  * a requirements spec (AQA-SRS) with one requirement per capability area,
  * coverage links from each requirement to the test cases that exercise it
    (so the traceability matrix is populated and coverage gaps -> 0),
  * the CI run plan filled with every case, ordered by architectural layer and
    prioritised by urgency (so get_run_manifest returns a real run list),
  * dependency edges between representative gate cases (project -> suite ->
    case -> execution; mcp wraps the service layer) so gating is exercised.

Everything goes through the public service layer and is idempotent — safe to
re-run after a reset or after scripts/dogfood.py adds new cases.
"""

import asyncio

from sqlalchemy import select

from app.db import SessionLocal
from app.models.structure import Project
from app.schemas.requirement import ReqSpecCreate, RequirementCreate
from app.services import plans, requirements, suites, testcases

PROJECT_PREFIX = "AQA"
PLAN_NAME = "CI"
SPEC_DOC_ID = "AQA-SRS"
SPEC_NAME = "AgentQA Platform — Software Requirements"

# requirement doc id -> (name, suites whose cases cover it)
REQUIREMENTS: list[tuple[str, str, list[str]]] = [
    ("REQ-AUTH-1", "Authentication, JWT sessions, and agent API keys", ["auth"]),
    ("REQ-PROJ-1", "Projects and hierarchical test suites", ["projects", "suites"]),
    ("REQ-CASE-1", "Versioned test cases with ordered steps", ["testcases"]),
    ("REQ-PLAN-1", "Test plans, builds, and milestones", ["plans", "builds", "milestones"]),
    ("REQ-EXEC-1", "Execution recording, results, and build upsert", ["executions"]),
    ("REQ-ASSIGN-1", "Work assignment to humans and agents", ["assignments", "mcp_assignments"]),
    ("REQ-MCP-1", "MCP agent interface over the shared service layer", ["mcp"]),
    ("REQ-PLATFORM-1", "Platform / environment management", ["platforms"]),
    ("REQ-CLI-1", "CLI coverage of the REST surface", ["cli"]),
    ("REQ-SVC-1", "Transport-agnostic service-layer integrity", ["services"]),
    ("REQ-SEED-1", "Seed / bootstrap of roles and admin", ["seed"]),
]

# run-plan layers in architectural order: (suites, urgency 1=low 2=med 3=high)
PLAN_LAYERS: list[tuple[list[str], int]] = [
    (["auth", "services", "seed"], 3),
    (["projects", "suites", "testcases", "platforms"], 3),
    (["plans", "builds", "milestones"], 2),
    (["executions"], 3),
    (["assignments", "mcp_assignments"], 2),
    (["mcp", "cli"], 2),
]

# dependency edges between suites' gate cases: (dependent_suite, prerequisite_suite)
DEPENDENCIES: list[tuple[str, str]] = [
    ("suites", "projects"),
    ("testcases", "suites"),
    ("executions", "testcases"),
    ("mcp", "testcases"),
    ("plans", "projects"),
    ("builds", "plans"),
]


async def _get_project(session):
    proj = (
        await session.execute(select(Project).where(Project.prefix == PROJECT_PREFIX))
    ).scalar_one_or_none()
    if proj is None:
        raise SystemExit(
            f"No '{PROJECT_PREFIX}' project — run scripts/dogfood.py first to catalog the suite."
        )
    return proj


async def _get_or_create_plan(session, project_id: int):
    for existing in await plans.list_plans(session, project_id):
        if existing.name == PLAN_NAME:
            return existing
    from app.schemas.plan import PlanCreate

    return await plans.create_plan(session, project_id, PlanCreate(name=PLAN_NAME))


async def _suite_cases(session, project_id: int) -> dict[str, list[int]]:
    """suite name -> case ids (ordered), for the project."""
    out: dict[str, list[int]] = {}
    for s in await suites.list_suites(session, project_id):
        cases = await testcases.list_cases_in_suite(session, s.id)
        out[s.name] = [c.id for c in cases]
    return out


async def main() -> None:
    async with SessionLocal() as session:
        proj = await _get_project(session)
        plan = await _get_or_create_plan(session, proj.id)
        suite_cases = await _suite_cases(session, proj.id)

        # 1. requirements spec (idempotent by doc_id)
        existing_specs = await requirements.list_req_specs(session, proj.id)
        spec = next((s for s in existing_specs if s.doc_id == SPEC_DOC_ID), None)
        if spec is None:
            spec = await requirements.create_req_spec(
                session, proj.id, ReqSpecCreate(doc_id=SPEC_DOC_ID, name=SPEC_NAME)
            )

        # 2. requirements + coverage (idempotent by req_doc_id; coverage skips dups)
        reqs_in_spec = await requirements.list_requirements(session, spec.id)
        existing_reqs = {r.req_doc_id: r for r in reqs_in_spec}
        req_count = cov_count = 0
        for doc_id, name, suite_names in REQUIREMENTS:
            case_ids = [cid for sn in suite_names for cid in suite_cases.get(sn, [])]
            if doc_id in existing_reqs:
                links = await requirements.link_requirement_coverage(
                    session, existing_reqs[doc_id].id, case_ids
                )
            else:
                await requirements.create_requirement(
                    session,
                    spec.id,
                    RequirementCreate(req_doc_id=doc_id, name=name, link_to_cases=case_ids),
                )
                req_count += 1
                links = case_ids
            cov_count += len(links)

        # 3. fill the run plan, layer by layer, with urgency (add_cases appends in
        #    order and is idempotent — re-adding an existing case is a no-op)
        for suite_names, urgency in PLAN_LAYERS:
            ids = [cid for sn in suite_names for cid in suite_cases.get(sn, [])]
            if ids:
                await plans.add_cases(session, plan.id, ids, urgency=urgency)

        # 4. dependency edges between suite gate cases (first case per suite)
        dep_count = 0
        for dependent, prereq in DEPENDENCIES:
            dep_cases = suite_cases.get(dependent, [])
            pre_cases = suite_cases.get(prereq, [])
            if dep_cases and pre_cases:
                await testcases.add_dependency(session, dep_cases[0], pre_cases[0])
                dep_count += 1

        # 5. report back through the service layer
        gaps = await requirements.get_coverage_gaps(session, proj.id)
        manifest = await plans.get_run_manifest(session, plan.id)

    print(f"project={proj.name} (#{proj.id})  spec={SPEC_DOC_ID}  plan={PLAN_NAME} (#{plan.id})")
    print(f"requirements: +{req_count} new (total {len(REQUIREMENTS)})  coverage_links={cov_count}")
    print(f"run plan: {len(manifest)} cases  dependencies={dep_count}")
    print(f"coverage_gaps={len(gaps)}")


if __name__ == "__main__":
    asyncio.run(main())
