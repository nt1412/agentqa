from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requirement import ReqSpec, Requirement, ReqVersion
from app.schemas.requirement import (
    ReqSpecCreate,
    RequirementCreate,
    RequirementOut,
    ReqVersionOut,
)
from app.services.errors import NotFound
from app.services.projects import get_project


async def create_req_spec(session: AsyncSession, project_id: int, data: ReqSpecCreate) -> ReqSpec:
    await get_project(session, project_id)
    spec = ReqSpec(project_id=project_id, doc_id=data.doc_id, name=data.name, scope=data.scope)
    session.add(spec)
    await session.commit()
    await session.refresh(spec)
    return spec


async def list_req_specs(session: AsyncSession, project_id: int) -> list[ReqSpec]:
    stmt = select(ReqSpec).where(ReqSpec.project_id == project_id).order_by(ReqSpec.id)
    return list((await session.execute(stmt)).scalars().all())


async def create_requirement(session: AsyncSession, spec_id: int, data: RequirementCreate):
    spec = await session.get(ReqSpec, spec_id)
    if spec is None:
        raise NotFound(f"req spec {spec_id} not found")
    req = Requirement(spec_id=spec_id, req_doc_id=data.req_doc_id, name=data.name)
    session.add(req)
    await session.flush()
    version = ReqVersion(req_id=req.id, version=1, scope=data.scope, status="draft")
    session.add(version)
    await session.flush()

    if data.link_to_cases:
        from app.services.requirements import link_coverage

        await link_coverage(session, version.id, data.link_to_cases)
    await session.commit()
    return await get_requirement(session, req.id)


async def _current_req_version(session: AsyncSession, req: Requirement) -> ReqVersion | None:
    stmt = select(ReqVersion).where(ReqVersion.req_id == req.id).order_by(ReqVersion.version.desc())
    return (await session.execute(stmt)).scalars().first()


async def get_requirement(session: AsyncSession, req_id: int) -> RequirementOut:
    req = await session.get(Requirement, req_id)
    if req is None:
        raise NotFound(f"requirement {req_id} not found")
    out = RequirementOut.model_validate(req)
    cur = await _current_req_version(session, req)
    out.current_version = ReqVersionOut.model_validate(cur) if cur else None
    return out


async def list_requirements(session: AsyncSession, spec_id: int) -> list[Requirement]:
    stmt = select(Requirement).where(Requirement.spec_id == spec_id).order_by(Requirement.id)
    return list((await session.execute(stmt)).scalars().all())
