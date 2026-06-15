"""Compute-on-read lineage aggregations over the ``latest_result_per_build_case``
view (see ``app/db_views.py``). Build/commit/run rollups, build detail, and
per-case history — the data spine for the operator console.
"""

import datetime as dt

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import Build, TestPlan, TestPlanCase
from app.models.testcase import TestCase, TestCaseVersion
from app.services.builds import get_build, list_builds
from app.services.plans import get_plan
from app.services.projects import get_project

DEFAULT_BRANCH_FALLBACK = "main"


def _build_dump(build: Build) -> dict:
    return {
        "id": build.id,
        "plan_id": build.plan_id,
        "name": build.name,
        "branch": build.branch,
        "commit_id": build.commit_id,
        "base_commit": build.base_commit,
        "created_at": build.created_at.isoformat() if build.created_at else None,
    }


async def _plan_case_ids(session: AsyncSession, plan_id: int) -> set[int]:
    """Distinct test-case ids that are in a plan (across any linked version)."""
    rows = (
        await session.execute(
            select(TestCaseVersion.case_id)
            .join(TestPlanCase, TestPlanCase.version_id == TestCaseVersion.id)
            .where(TestPlanCase.plan_id == plan_id)
        )
    ).scalars().all()
    return set(rows)


async def _latest_results(session: AsyncSession, build_id: int) -> dict[int, str]:
    """case_id -> latest status in this build, from the single-definition view."""
    rows = (
        await session.execute(
            text(
                "SELECT case_id, status FROM latest_result_per_build_case "
                "WHERE build_id = :b"
            ),
            {"b": build_id},
        )
    ).all()
    return {case_id: status for case_id, status in rows}


async def build_rollup(session: AsyncSession, build_id: int) -> dict:
    """Pass/fail/blocked/not_run counts + pass_rate for one build.

    Counts are over the LATEST result per case in the build (so a case run twice
    counts once). ``not_run`` is plan cases with no result in this build;
    ``pass_rate`` is pass / plan_cases (a build that skipped half the plan is not
    100% just because what ran passed).
    """
    build = await get_build(session, build_id)  # raises NotFound
    results = await _latest_results(session, build_id)
    plan_case_ids = await _plan_case_ids(session, build.plan_id)

    passed = sum(1 for s in results.values() if s == "pass")
    failed = sum(1 for s in results.values() if s == "fail")
    blocked = sum(1 for s in results.values() if s == "blocked")
    not_run = sum(1 for cid in plan_case_ids if cid not in results)
    plan_cases = len(plan_case_ids)
    pass_rate = round(100 * passed / plan_cases) if plan_cases else 0
    return {
        "build_id": build_id,
        "plan_id": build.plan_id,
        "pass": passed,
        "fail": failed,
        "blocked": blocked,
        "not_run": not_run,
        "executed": len(results),
        "plan_cases": plan_cases,
        "pass_rate": pass_rate,
    }


async def build_detail(session: AsyncSession, build_id: int) -> dict:
    """Build header + rollup + each case's LATEST result in the build."""
    build = await get_build(session, build_id)
    rollup = await build_rollup(session, build_id)
    rows = (
        await session.execute(
            text(
                "SELECT r.case_id, r.status, r.execution_id, r.duration, "
                "       c.external_id, c.name "
                "FROM latest_result_per_build_case r "
                "JOIN test_cases c ON c.id = r.case_id "
                "WHERE r.build_id = :b ORDER BY c.external_id"
            ),
            {"b": build_id},
        )
    ).all()
    cases = [
        {
            "case_id": cid,
            "status": status,
            "execution_id": eid,
            "duration": duration,
            "external_id": ext,
            "name": name,
        }
        for cid, status, eid, duration, ext, name in rows
    ]
    return {"build": _build_dump(build), "rollup": rollup, "cases": cases}


async def case_history(session: AsyncSession, case_id: int) -> dict:
    """A case's latest result per build, chronological, with derived broke/fixed
    transitions (pass→fail = broke at that commit; fail/blocked→pass = fixed).
    The transitions are the "known regression path" the guard later surfaces.
    """
    rows = (
        await session.execute(
            text(
                "SELECT r.build_id, b.name, b.branch, b.commit_id, r.status, "
                "       r.execution_id, b.created_at "
                "FROM latest_result_per_build_case r "
                "JOIN builds b ON b.id = r.build_id "
                "WHERE r.case_id = :c ORDER BY b.created_at, b.id"
            ),
            {"c": case_id},
        )
    ).all()
    executions = [
        {
            "build_id": bid,
            "build_name": bname,
            "branch": branch,
            "commit_id": commit_id,
            "status": status,
            "execution_id": eid,
            "created_at": created_at.isoformat() if created_at else None,
        }
        for bid, bname, branch, commit_id, status, eid, created_at in rows
    ]
    transitions: list[dict] = []
    prev = None
    for e in executions:
        if prev is not None:
            if prev["status"] == "pass" and e["status"] in ("fail", "blocked"):
                transitions.append(
                    {"type": "broke", "commit_id": e["commit_id"], "build_id": e["build_id"]}
                )
            elif prev["status"] in ("fail", "blocked") and e["status"] == "pass":
                transitions.append(
                    {"type": "fixed", "commit_id": e["commit_id"], "build_id": e["build_id"]}
                )
        prev = e
    return {"case_id": case_id, "executions": executions, "transitions": transitions}


async def default_branch_for_plan(session: AsyncSession, plan_id: int) -> str:
    plan = await get_plan(session, plan_id)
    project = await get_project(session, plan.project_id)
    return (project.options or {}).get("default_branch", DEFAULT_BRANCH_FALLBACK)


async def resolve_baseline(session: AsyncSession, build: Build) -> Build | None:
    """The default-branch build (in the same plan) this branch build is judged
    against. Precise when base_commit matches a default-branch build; otherwise
    the latest default-branch build at or before this build's created_at. None
    when there is no default-branch build to compare against (→ "all new").
    """
    default_branch = await default_branch_for_plan(session, build.plan_id)
    candidates = (
        await session.execute(
            select(Build).where(
                Build.plan_id == build.plan_id,
                Build.branch == default_branch,
                Build.id != build.id,
            )
        )
    ).scalars().all()
    if not candidates:
        return None
    # precise: pin to the recorded merge-base if that build exists
    if build.base_commit:
        for c in candidates:
            if c.commit_id == build.base_commit:
                return c
    # fallback: latest default-branch build at/before this build's time
    eligible = [
        c for c in candidates
        if c.created_at and build.created_at and c.created_at <= build.created_at
    ] or candidates
    eligible.sort(key=lambda c: (c.created_at, c.id))
    return eligible[-1]


async def _case_meta(session: AsyncSession, case_ids: set[int]) -> dict[int, tuple]:
    if not case_ids:
        return {}
    rows = (
        await session.execute(
            text(
                "SELECT id, external_id, name FROM test_cases WHERE id = ANY(:ids)"
            ),
            {"ids": list(case_ids)},
        )
    ).all()
    return {cid: (ext, name) for cid, ext, name in rows}


_DIFF_CLASSES = (
    "regression",
    "fixed",
    "still_failing",
    "still_passing",
    "new_test",
    "removed",
)


def _classify(baseline_status: str | None, build_status: str | None) -> str:
    if baseline_status is None and build_status is not None:
        return "new_test"  # new coverage on this branch — NOT a regression
    if build_status is None and baseline_status is not None:
        return "removed"
    if baseline_status == "pass" and build_status in ("fail", "blocked"):
        return "regression"  # you broke it
    if baseline_status in ("fail", "blocked") and build_status == "pass":
        return "fixed"
    if baseline_status in ("fail", "blocked") and build_status in ("fail", "blocked"):
        return "still_failing"
    return "still_passing"


async def compare(session: AsyncSession, build_id: int, to: int | str = "baseline") -> dict:
    """Classify each case between a build and another build (or its baseline).

    ``to`` is a build id, or "baseline" to auto-resolve the default-branch build.
    Each case is exactly one of: regression / fixed / still_failing /
    still_passing / new_test / removed. A regression (baseline pass → fail) is
    never conflated with a new_test (no baseline result).
    """
    build = await get_build(session, build_id)
    if to == "baseline":
        baseline = await resolve_baseline(session, build)
    else:
        baseline = await get_build(session, int(to))
    cur = await _latest_results(session, build_id)
    base = await _latest_results(session, baseline.id) if baseline else {}

    classes: dict[str, list] = {k: [] for k in _DIFF_CLASSES}
    meta = await _case_meta(session, set(cur) | set(base))
    for cid in sorted(set(cur) | set(base), key=lambda x: meta.get(x, ("", ""))[0]):
        b_status = cur.get(cid)
        a_status = base.get(cid)
        ext, name = meta.get(cid, (None, None))
        classes[_classify(a_status, b_status)].append(
            {
                "case_id": cid,
                "external_id": ext,
                "name": name,
                "baseline_status": a_status,
                "build_status": b_status,
            }
        )
    return {
        "build_id": build_id,
        "baseline_build_id": baseline.id if baseline else None,
        "classes": classes,
    }


async def _quarantined_ids(session: AsyncSession, project_id: int) -> set[int]:
    rows = (
        await session.execute(
            select(TestCase.id).where(
                TestCase.project_id == project_id, TestCase.quarantined.is_(True)
            )
        )
    ).scalars().all()
    return set(rows)


async def branch_status(
    session: AsyncSession, project_id: int, window_days: int = 14
) -> list[dict]:
    """Merge-readiness per active branch (builds in the trailing window, excluding
    the default branch).

    The verdict is taken at the grain of (branch, head-commit) and **summed across
    every plan** that ran at that commit — BLOCKED if ANY plan regresses, else
    READY. "Latest build per branch" would false-green a branch whose Smoke plan is
    green while its Regression plan holds a regression; this sums all of them.
    """
    project = await get_project(session, project_id)
    default_branch = (project.options or {}).get("default_branch", DEFAULT_BRANCH_FALLBACK)
    quarantined = await _quarantined_ids(session, project_id)
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=window_days)
    builds = (
        await session.execute(
            select(Build)
            .join(TestPlan, TestPlan.id == Build.plan_id)
            .where(
                TestPlan.project_id == project_id,
                Build.branch.isnot(None),
                Build.branch != default_branch,
                Build.created_at >= cutoff,
            )
        )
    ).scalars().all()

    by_branch: dict[str, list[Build]] = {}
    for b in builds:
        by_branch.setdefault(b.branch, []).append(b)

    result: list[dict] = []
    for branch, blds in by_branch.items():
        head = sorted(blds, key=lambda x: (x.created_at, x.id))[-1]
        head_commit = head.commit_id
        at_head = [b for b in blds if b.commit_id == head_commit]
        regressions = fixed = new_test = 0
        plan_breakdown: list[dict] = []
        for b in at_head:
            diff = await compare(session, b.id, "baseline")
            # quarantined cases never count toward the verdict (known-flaky noise)
            r = len([e for e in diff["classes"]["regression"] if e["case_id"] not in quarantined])
            f = len(diff["classes"]["fixed"])
            n = len(diff["classes"]["new_test"])
            regressions += r
            fixed += f
            new_test += n
            plan_breakdown.append(
                {
                    "plan_id": b.plan_id,
                    "build_id": b.id,
                    "baseline_build_id": diff["baseline_build_id"],
                    "regressions": r,
                    "fixed": f,
                    "new_test": n,
                }
            )
        result.append(
            {
                "branch": branch,
                "head_commit": head_commit,
                "verdict": "BLOCKED" if regressions > 0 else "READY",
                "regressions": regressions,
                "fixed": fixed,
                "new_test": new_test,
                "plans": plan_breakdown,
            }
        )
    result.sort(key=lambda x: x["branch"])
    return result


async def known_fix_path(session: AsyncSession, case_id: int) -> dict | None:
    """If this case broke and was fixed before, return that completed path:
    {broke_commit, fixed_commit, fixing_execution_id, reasoning}. None if novel.

    This is the cached expensive answer — an agent reads it instead of
    re-investigating a failure that's been diagnosed and fixed once already.
    """
    hist = await case_history(session, case_id)
    pairs: list[tuple] = []
    last_broke = None
    for t in hist["transitions"]:
        if t["type"] == "broke":
            last_broke = t
        elif t["type"] == "fixed" and last_broke is not None:
            pairs.append((last_broke, t))
            last_broke = None
    if not pairs:
        return None
    broke_t, fixed_t = pairs[-1]  # most recent completed broke→fixed
    exec_id = next(
        (e["execution_id"] for e in hist["executions"] if e["build_id"] == fixed_t["build_id"]),
        None,
    )
    reasoning = None
    if exec_id is not None:
        row = (
            await session.execute(
                text(
                    "SELECT reasoning FROM execution_reasoning "
                    "WHERE execution_id = :e ORDER BY id DESC LIMIT 1"
                ),
                {"e": exec_id},
            )
        ).first()
        if row:
            reasoning = row[0]
    return {
        "broke_commit": broke_t["commit_id"],
        "fixed_commit": fixed_t["commit_id"],
        "fixing_execution_id": exec_id,
        "reasoning": reasoning,
    }


async def known_regressions(
    session: AsyncSession,
    project_id: int,
    branch: str | None = None,
    case_ids: list[int] | None = None,
    window_days: int = 14,
) -> list[dict]:
    """Open regressions on active branches, each annotated with its known fix-path
    (broke@→fixed@ + prior reasoning) when one exists. The pre-flight an agent
    calls before investigating — empty when nothing is regressing."""
    project = await get_project(session, project_id)
    default_branch = (project.options or {}).get("default_branch", DEFAULT_BRANCH_FALLBACK)
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=window_days)
    q = (
        select(Build)
        .join(TestPlan, TestPlan.id == Build.plan_id)
        .where(
            TestPlan.project_id == project_id,
            Build.branch.isnot(None),
            Build.branch != default_branch,
            Build.created_at >= cutoff,
        )
    )
    if branch:
        q = q.where(Build.branch == branch)
    blds = (await session.execute(q)).scalars().all()

    by_branch: dict[str, list[Build]] = {}
    for b in blds:
        by_branch.setdefault(b.branch, []).append(b)

    quarantined = await _quarantined_ids(session, project_id)
    case_filter = set(case_ids) if case_ids else None
    out: list[dict] = []
    for br, lst in by_branch.items():
        head_commit = sorted(lst, key=lambda x: (x.created_at, x.id))[-1].commit_id
        for b in [x for x in lst if x.commit_id == head_commit]:
            diff = await compare(session, b.id, "baseline")
            for entry in diff["classes"]["regression"]:
                if entry["case_id"] in quarantined:
                    continue  # known-flaky — don't surface as something to investigate
                if case_filter and entry["case_id"] not in case_filter:
                    continue
                out.append(
                    {
                        "branch": br,
                        "plan_id": b.plan_id,
                        "build_id": b.id,
                        "case_id": entry["case_id"],
                        "external_id": entry["external_id"],
                        "name": entry["name"],
                        "fix_path": await known_fix_path(session, entry["case_id"]),
                    }
                )
    out.sort(key=lambda x: (x["branch"], x["external_id"] or ""))
    return out


async def list_builds_enriched(session: AsyncSession, plan_id: int) -> list[dict]:
    """Builds for a plan, newest first, each with its rollup — the build timeline."""
    builds = await list_builds(session, plan_id)
    ordered = sorted(builds, key=lambda b: (b.created_at, b.id), reverse=True)
    out: list[dict] = []
    for b in ordered:
        d = _build_dump(b)
        d["rollup"] = await build_rollup(session, b.id)
        out.append(d)
    return out
