"""Backfill AQA's own requirements, coverage, and run-plan hierarchy into the AQA
dogfood project — through the **front door** (REST), so the platform tracks its own
development using the same surface agents use.

Complements scripts/dogfood.py (which catalogs the pytest suite + records runs):
  * a requirements spec (AQA-SRS) with one requirement per capability area,
  * coverage links from each requirement to the cases that exercise it,
  * the CI run plan filled with every case, ordered by layer and urgency,
  * dependency edges between representative gate cases.

Idempotent (server-side find-or-create / dedup). Run scripts/dogfood.py first so
the project + cases exist. Auth via scripts/_aqaclient (AQA_API_KEY or admin login).
"""

from scripts._aqaclient import auth, get, post

PROJECT_PREFIX = "AQA"
PLAN_NAME = "CI"
SPEC_DOC_ID = "AQA-SRS"
SPEC_NAME = "AQA Platform — Software Requirements"

REQUIREMENTS: list[tuple[str, str, list[str]]] = [
    ("REQ-AUTH-1", "Authentication, JWT sessions, and agent identities", ["auth", "users"]),
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
    (
        "REQ-EVIDENCE-1",
        "Evidence, artifacts, claims & audit",
        [
            "evidence_verify", "evidence_bundle", "evidence_artifacts",
            "evidence_claims", "evidence_audit", "mcp_evidence", "storage",
        ],
    ),
    (
        "REQ-TRACE-1",
        "Requirements, coverage & traceability",
        ["requirements", "coverage", "mcp_requirements"],
    ),
    (
        "REQ-SELFCORRECT-1",
        "Failure context & similar-failure search",
        ["failure_context", "similar_failures", "mcp_failure", "embeddings"],
    ),
    ("REQ-HIER-1", "Test hierarchy, ordering & dependency gating", ["hierarchy", "mcp_hierarchy"]),
]

PLAN_LAYERS: list[tuple[list[str], int]] = [
    (["auth", "services", "seed", "users"], 3),
    (["projects", "suites", "testcases", "platforms"], 3),
    (["plans", "builds", "milestones"], 2),
    (["executions"], 3),
    (["assignments", "mcp_assignments"], 2),
    (["mcp", "cli"], 2),
]

DEPENDENCIES: list[tuple[str, str]] = [
    ("suites", "projects"),
    ("testcases", "suites"),
    ("executions", "testcases"),
    ("mcp", "testcases"),
    ("plans", "projects"),
    ("builds", "plans"),
]


def main() -> None:
    auth()
    proj = next((p for p in get("/api/v1/projects") if p["prefix"] == PROJECT_PREFIX), None)
    if proj is None:
        raise SystemExit(f"No '{PROJECT_PREFIX}' project — run scripts/dogfood.py first.")
    pid = proj["id"]

    plan = next((p for p in get(f"/api/v1/projects/{pid}/plans") if p["name"] == PLAN_NAME), None)
    if plan is None:
        plan = post(f"/api/v1/projects/{pid}/plans", {"name": PLAN_NAME})
    plan_id = plan["id"]

    # suite name -> ordered case ids
    suite_cases: dict[str, list[int]] = {}
    for s in get(f"/api/v1/projects/{pid}/suites"):
        suite_cases[s["name"]] = [c["id"] for c in get(f"/api/v1/suites/{s['id']}/cases")]

    # self-healing catch-alls so coverage/plan never silently drift
    mapped = {s for _, _, names in REQUIREMENTS for s in names}
    extra = sorted(set(suite_cases) - mapped)
    requirements_to_apply = list(REQUIREMENTS)
    if extra:
        requirements_to_apply.append(
            ("REQ-MISC-1", "Other test coverage (auto-mapped suites)", extra)
        )
    planned = {s for names, _ in PLAN_LAYERS for s in names}
    plan_layers = list(PLAN_LAYERS)
    extra_plan = sorted(set(suite_cases) - planned)
    if extra_plan:
        plan_layers.append((extra_plan, 2))

    # 1. spec (idempotent by doc_id)
    spec = next(
        (s for s in get(f"/api/v1/projects/{pid}/req-specs") if s["doc_id"] == SPEC_DOC_ID), None
    )
    if spec is None:
        spec = post(
            f"/api/v1/projects/{pid}/req-specs", {"doc_id": SPEC_DOC_ID, "name": SPEC_NAME}
        )
    spec_id = spec["id"]

    # 2. requirements + coverage (create new, link coverage on existing — both idempotent)
    existing = {r["req_doc_id"]: r["id"] for r in get(f"/api/v1/req-specs/{spec_id}/requirements")}
    req_count = cov_count = 0
    for doc_id, name, suite_names in requirements_to_apply:
        case_ids = [cid for sn in suite_names for cid in suite_cases.get(sn, [])]
        if doc_id in existing:
            if case_ids:
                post(f"/api/v1/requirements/{existing[doc_id]}/coverage", {"case_ids": case_ids})
        else:
            post(
                f"/api/v1/req-specs/{spec_id}/requirements",
                {"req_doc_id": doc_id, "name": name, "link_to_cases": case_ids},
            )
            req_count += 1
        cov_count += len(case_ids)

    # 3. fill the run plan, layer by layer (add-cases is idempotent)
    for suite_names, urgency in plan_layers:
        ids = [cid for sn in suite_names for cid in suite_cases.get(sn, [])]
        if ids:
            post(f"/api/v1/plans/{plan_id}/cases", {"case_ids": ids, "urgency": urgency})

    # 4. dependency edges between suite gate cases (first case per suite)
    dep_count = 0
    for dependent, prereq in DEPENDENCIES:
        dep_cases = suite_cases.get(dependent, [])
        pre_cases = suite_cases.get(prereq, [])
        if dep_cases and pre_cases:
            try:
                post(
                    f"/api/v1/cases/{dep_cases[0]}/dependencies",
                    {"depends_on_case_id": pre_cases[0]},
                )
                dep_count += 1
            except Exception:  # noqa: BLE001 — idempotent re-run; edge may already exist
                pass

    # 5. report through the front door
    gaps = get(f"/api/v1/projects/{pid}/coverage-gaps")
    manifest = get(f"/api/v1/plans/{plan_id}/manifest")
    covered: set[int] = set()
    for row in get(f"/api/v1/projects/{pid}/traceability"):
        covered |= set(row["covered_case_ids"])
    all_cases = {cid for ids in suite_cases.values() for cid in ids}
    uncovered = len(all_cases - covered)

    print(f"project={proj['name']} (#{pid})  spec={SPEC_DOC_ID}  plan={PLAN_NAME} (#{plan_id})")
    print(f"requirements: +{req_count} new  coverage_links~={cov_count}  (via REST)")
    print(f"run plan: {len(manifest)} cases  dependencies={dep_count}")
    print(f"coverage_gaps={len(gaps)}  uncovered_cases={uncovered}")


if __name__ == "__main__":
    main()
