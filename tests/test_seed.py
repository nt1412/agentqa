import pytest
from sqlalchemy import select

from app.models.user import Role, User
from scripts.seed import seed_defaults


@pytest.mark.asyncio
async def test_seed_creates_roles_and_admin(session):
    await seed_defaults(session, admin_login="admin", admin_password="admin")
    roles = (await session.execute(select(Role))).scalars().all()
    assert {r.name for r in roles} >= {"Admin", "Project Lead", "Test Designer", "Tester", "Guest"}
    admin = (await session.execute(select(User).where(User.login == "admin"))).scalar_one()
    assert admin.password_hash is not None

    # idempotent: second call does not duplicate
    await seed_defaults(session, admin_login="admin", admin_password="admin")
    admins = (await session.execute(select(User).where(User.login == "admin"))).scalars().all()
    assert len(admins) == 1
