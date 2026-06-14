import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models.user import Role, User
from app.services import auth

DEFAULT_ROLES = ["Admin", "Project Lead", "Test Designer", "Tester", "Guest"]


async def seed_defaults(session: AsyncSession, admin_login: str, admin_password: str) -> None:
    existing_roles = {r.name for r in (await session.execute(select(Role))).scalars().all()}
    for name in DEFAULT_ROLES:
        if name not in existing_roles:
            session.add(Role(name=name))
    await session.flush()
    admin_role = (await session.execute(select(Role).where(Role.name == "Admin"))).scalar_one()

    admin = (
        await session.execute(select(User).where(User.login == admin_login))
    ).scalar_one_or_none()
    if admin is None:
        admin = User(
            login=admin_login,
            password_hash=auth.hash_password(admin_password),
            auth_method="db",
            role_id=admin_role.id,
            active=True,
        )
        session.add(admin)
    await session.commit()


async def _main() -> None:
    async with SessionLocal() as session:
        await seed_defaults(session, admin_login="admin", admin_password="admin")
    print("seeded default roles + admin (admin/admin)")


if __name__ == "__main__":
    asyncio.run(_main())
