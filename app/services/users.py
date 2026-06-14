from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services import auth
from app.services.errors import Conflict, NotFound


async def register_agent(
    session: AsyncSession,
    login: str,
    agent_model: str | None = None,
    email: str | None = None,
    display_name: str | None = None,
) -> tuple[User, str]:
    """Create an agent identity (``auth_method='agent'``) with a fresh API key.

    Returns ``(user, plaintext_api_key)``. The plaintext key is available only
    here; only its sha256 hash is persisted (see :func:`auth.hash_api_key`), so
    the caller must capture it now if they want to use the REST API.
    """
    existing = (
        await session.execute(select(User).where(User.login == login))
    ).scalar_one_or_none()
    if existing:
        raise Conflict(f"user login '{login}' already exists")

    api_key = auth.generate_api_key()
    user = User(
        login=login,
        auth_method="agent",
        agent_model=agent_model,
        email=email,
        first=display_name,
        api_key=auth.hash_api_key(api_key),
        active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user, api_key


async def list_agents(session: AsyncSession) -> list[User]:
    """All agent identities (auth_method='agent'), newest last."""
    rows = await session.execute(
        select(User).where(User.auth_method == "agent").order_by(User.id)
    )
    return list(rows.scalars().all())


async def deactivate_user(session: AsyncSession, user_id: int) -> User:
    """Soft-delete: mark a user inactive so it can no longer authenticate and
    drops from active lists, while its recorded work stays attributable.
    Idempotent (deactivating an already-inactive user is a no-op)."""
    user = await session.get(User, user_id)
    if user is None:
        raise NotFound(f"user {user_id} not found")
    user.active = False
    await session.commit()
    await session.refresh(user)
    return user
