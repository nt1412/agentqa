"""Re-run requests: a human (or agent) asks for a case/build to be re-run, which
becomes an ``assignment`` of type 'rerun'. Humans and agents share one work
queue — agents discover requests via the existing ``list_assignments`` — so the
collaboration loop is concrete: a human flags a regression, an agent picks it up.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import TestPlanCase
from app.models.testcase import TestCaseVersion
from app.models.user import Assignment
from app.services.builds import get_build


async def _open_rerun_exists(session: AsyncSession, case_id: int, build_id: int) -> bool:
    row = (
        await session.execute(
            select(Assignment.id).where(
                Assignment.type == "rerun",
                Assignment.case_id == case_id,
                Assignment.build_id == build_id,
                Assignment.status == "open",
            )
        )
    ).first()
    return row is not None


async def request_rerun(
    session: AsyncSession,
    *,
    build_id: int,
    assignee_id: int,
    assigner_id: int | None,
    case_id: int | None = None,
    assignee_type: str = "agent",
) -> list[Assignment]:
    """Request a re-run of one case (case_id given) or every case in the build's
    plan (case_id omitted). Idempotent: skips any case that already has an open
    rerun for this build, so re-requesting never duplicates work.
    """
    build = await get_build(session, build_id)  # raises NotFound
    plan_id = build.plan_id
    if case_id is not None:
        case_ids = [case_id]
    else:
        rows = (
            await session.execute(
                select(TestCaseVersion.case_id)
                .join(TestPlanCase, TestPlanCase.version_id == TestCaseVersion.id)
                .where(TestPlanCase.plan_id == plan_id)
            )
        ).scalars().all()
        case_ids = list(dict.fromkeys(rows))  # distinct, order-preserving

    created: list[Assignment] = []
    for cid in case_ids:
        if await _open_rerun_exists(session, cid, build_id):
            continue
        a = Assignment(
            type="rerun",
            case_id=cid,
            plan_id=plan_id,
            build_id=build_id,
            assignee_id=assignee_id,
            assignee_type=assignee_type,
            status="open",
            assigner_id=assigner_id,
        )
        session.add(a)
        created.append(a)
    if created:
        await session.commit()
        for a in created:
            await session.refresh(a)
    return created
