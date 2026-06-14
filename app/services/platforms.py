from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.structure import Platform
from app.schemas.platform import PlatformCreate
from app.services.errors import NotFound
from app.services.projects import get_project


async def create_platform(session: AsyncSession, project_id: int, data: PlatformCreate) -> Platform:
    await get_project(session, project_id)  # raises NotFound if absent
    platform = Platform(project_id=project_id, name=data.name, notes=data.notes)
    session.add(platform)
    await session.commit()
    await session.refresh(platform)
    return platform


async def get_platform(session: AsyncSession, platform_id: int) -> Platform:
    platform = await session.get(Platform, platform_id)
    if platform is None:
        raise NotFound(f"platform {platform_id} not found")
    return platform


async def list_platforms(session: AsyncSession, project_id: int) -> list[Platform]:
    stmt = select(Platform).where(Platform.project_id == project_id).order_by(Platform.id)
    return list((await session.execute(stmt)).scalars().all())
