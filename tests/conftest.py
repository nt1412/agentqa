import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text

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
