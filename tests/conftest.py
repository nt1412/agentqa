import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

from sqlalchemy import delete

from app.db import get_session
from app.main import create_app
from app.models.user import User
from app.services import auth as auth_service

import app.models  # noqa: F401  ensure all models are registered
from app.models.base import Base

TEST_DB_URL = "postgresql+asyncpg://agentqa:agentqa@localhost:5432/agentqa_test"
ADMIN_URL = "postgresql+asyncpg://agentqa:agentqa@localhost:5432/agentqa"


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_test_db():
    admin = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text("DROP DATABASE IF EXISTS agentqa_test"))
        await conn.execute(text("CREATE DATABASE agentqa_test"))
    await admin.dispose()
    yield
    admin = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text("DROP DATABASE IF EXISTS agentqa_test"))
    await admin.dispose()


@pytest_asyncio.fixture(scope="session")
async def engine(_create_test_db):
    eng = create_async_engine(TEST_DB_URL)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with maker() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def app(session):
    application = create_app()

    async def _override_session():
        yield session

    application.dependency_overrides[get_session] = _override_session
    return application


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def user(session) -> User:
    u = User(
        login="alice",
        password_hash=auth_service.hash_password("pw"),
        email="alice@example.com",
        auth_method="db",
        active=True,
    )
    session.add(u)
    await session.commit()
    await session.refresh(u)
    yield u
    await session.execute(delete(User).where(User.id == u.id))
    await session.commit()


@pytest_asyncio.fixture
async def auth_headers(client, user) -> dict:
    resp = await client.post("/api/v1/auth/login", json={"login": "alice", "password": "pw"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
