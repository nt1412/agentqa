from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.execution import Execution, ExecutionStep
from app.models.plan import Build, TestPlan
from app.models.testcase import TestCase, TestCaseVersion, TestStep
from app.schemas.execution import ExecutionCreate
from app.services.errors import NotFound, ValidationFailed
from app.services.evidence import record_claims_and_reasoning


async def _resolve_case(session: AsyncSession, data: ExecutionCreate) -> TestCase:
    if data.case_id is not None:
        tc = await session.get(TestCase, data.case_id)
        if tc is None:
            raise NotFound(f"test case {data.case_id} not found")
        return tc
    if data.external_id is not None and data.project_id is not None:
        stmt = select(TestCase).where(
            TestCase.project_id == data.project_id,
            TestCase.external_id == data.external_id,
        )
        tc = (await session.execute(stmt)).scalar_one_or_none()
        if tc is None:
            raise NotFound(f"test case '{data.external_id}' not found")
        return tc
    raise ValidationFailed("provide case_id, or external_id + project_id")


async def _current_version_id(session: AsyncSession, case_id: int) -> int:
    stmt = (
        select(TestCaseVersion)
        .where(TestCaseVersion.case_id == case_id, TestCaseVersion.active.is_(True))
        .order_by(TestCaseVersion.version.desc())
    )
    v = (await session.execute(stmt)).scalars().first()
    if v is None:
        raise NotFound(f"test case {case_id} has no active version")
    return v.id


async def _upsert_build(
    session: AsyncSession, plan_id: int | None, build_name: str, commit_id: str | None
) -> int | None:
    if plan_id is None:
        return None
    plan = await session.get(TestPlan, plan_id)
    if plan is None:
        raise NotFound(f"test plan {plan_id} not found")
    stmt = select(Build).where(Build.plan_id == plan_id, Build.name == build_name)
    build = (await session.execute(stmt)).scalar_one_or_none()
    if build is None:
        build = Build(plan_id=plan_id, name=build_name, commit_id=commit_id)
        session.add(build)
        await session.flush()
    elif commit_id and not build.commit_id:
        build.commit_id = commit_id
    return build.id


async def record_execution(
    session: AsyncSession, data: ExecutionCreate, tester_id: int | None
) -> Execution:
    case = await _resolve_case(session, data)
    version_id = await _current_version_id(session, case.id)
    build_id = await _upsert_build(session, data.plan_id, data.build_name, data.commit_id)

    execution = Execution(
        plan_id=data.plan_id,
        version_id=version_id,
        build_id=build_id,
        tester_id=tester_id,
        execution_type="automated" if tester_id is None else "manual",
        status=data.status,
        notes=data.notes,
        duration=data.duration,
        session_id=data.session_id,
        run_id=data.run_id,
    )
    session.add(execution)
    await session.flush()

    if data.step_results:
        steps = (
            (await session.execute(select(TestStep).where(TestStep.version_id == version_id)))
            .scalars()
            .all()
        )
        by_number = {s.step_number: s.id for s in steps}
        for sr in data.step_results:
            step_id = by_number.get(sr.step_number)
            if step_id is None:
                raise ValidationFailed(f"step_number {sr.step_number} not in current version")
            session.add(
                ExecutionStep(
                    execution_id=execution.id,
                    step_id=step_id,
                    status=sr.status,
                    notes=sr.notes,
                )
            )
    await record_claims_and_reasoning(
        session,
        execution.id,
        data.claims,
        data.reasoning,
        data.agent_model,
        data.session_id,
    )
    await session.commit()
    return await _load(session, execution.id)


async def _load(session: AsyncSession, execution_id: int) -> Execution:
    stmt = (
        select(Execution).where(Execution.id == execution_id).options(selectinload(Execution.steps))
    )
    ex = (await session.execute(stmt)).scalar_one_or_none()
    if ex is None:
        raise NotFound(f"execution {execution_id} not found")
    return ex


async def get_execution(session: AsyncSession, execution_id: int) -> Execution:
    return await _load(session, execution_id)


async def list_for_case(session: AsyncSession, case_id: int) -> list[Execution]:
    version_ids = (
        (
            await session.execute(
                select(TestCaseVersion.id).where(TestCaseVersion.case_id == case_id)
            )
        )
        .scalars()
        .all()
    )
    if not version_ids:
        return []
    stmt = (
        select(Execution)
        .where(Execution.version_id.in_(version_ids))
        .order_by(Execution.created_at.desc())
        .options(selectinload(Execution.steps))
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_for_plan(session: AsyncSession, plan_id: int) -> list[Execution]:
    stmt = (
        select(Execution)
        .where(Execution.plan_id == plan_id)
        .order_by(Execution.created_at.desc())
        .options(selectinload(Execution.steps))
    )
    return list((await session.execute(stmt)).scalars().all())
