# AgentQA Platform — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational backend of AgentQA — a TestLink-equivalent test management platform for agentic coding — covering the database schema, FastAPI app, authentication, core CRUD (projects/suites/cases), basic execution recording, an MCP server, and a CLI.

**Architecture:** A single FastAPI application exposes a versioned REST API. All business logic lives in a **service layer** (`app/services/`) that is called by both the REST routers and the MCP server, so the two interfaces never duplicate logic. PostgreSQL (with the `pgvector` extension installed for later phases) is the system of record, accessed via SQLAlchemy 2.0 + Alembic migrations. The MCP server and CLI are thin clients over the service layer / REST API respectively. Everything runs under docker-compose.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, PostgreSQL 16 + pgvector, Pydantic v2, `python-jose` (JWT), `passlib[bcrypt]`, the official `mcp` SDK, `typer` + `httpx` (CLI), `pytest` + `pytest-asyncio` + `httpx.AsyncClient` (tests), `ruff` (lint/format).

**Scope note:** This plan covers **Phase 1 only**. Test plans, builds, the evidence/provenance tables, requirements, claims/verifications, embeddings/similarity, integrations, and the Next.js UI are explicitly deferred to later phases. The schema migration in this plan creates **all** tables (so later phases need no destructive migrations), but only the Phase-1 entities get services, endpoints, and tools.

---

## File Structure

```
agentqa/
├── docker-compose.yml              # postgres(+pgvector), api, minio
├── .env.example                    # all config keys
├── pyproject.toml                  # deps + ruff + pytest config
├── alembic.ini                     # alembic config
├── Dockerfile                      # api image
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app factory, router mounting
│   ├── config.py                   # pydantic-settings Settings
│   ├── db.py                       # async engine, session factory, get_session dep
│   ├── models/                     # SQLAlchemy ORM models, one file per domain
│   │   ├── __init__.py             # imports all models for Alembic autogen
│   │   ├── base.py                 # DeclarativeBase + TimestampMixin
│   │   ├── structure.py            # projects, test_suites, keywords, platforms
│   │   ├── testcase.py             # test_cases, versions, steps, relations, script_links
│   │   ├── plan.py                 # test_plans, builds, milestones, etc. (created, unused P1)
│   │   ├── execution.py            # executions, execution_steps, execution_bugs
│   │   ├── evidence.py             # artifacts, claims, verifications, reasoning, audit (P2)
│   │   ├── requirement.py          # req_specs, requirements, coverage (P2)
│   │   ├── user.py                 # users, roles, permissions, assignments
│   │   └── meta.py                 # custom_fields, attachments, integrations (P2+)
│   ├── schemas/                    # Pydantic request/response models
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── project.py
│   │   ├── suite.py
│   │   ├── testcase.py
│   │   └── execution.py
│   ├── services/                   # business logic — shared by REST + MCP
│   │   ├── __init__.py
│   │   ├── errors.py               # NotFound, Conflict, etc. (transport-agnostic)
│   │   ├── auth.py                 # hashing, JWT, api-key, current-user resolution
│   │   ├── projects.py
│   │   ├── suites.py
│   │   ├── testcases.py
│   │   └── executions.py
│   ├── api/                        # FastAPI routers (thin: parse → service → serialize)
│   │   ├── __init__.py
│   │   ├── deps.py                 # auth dependencies, session dependency
│   │   ├── auth.py
│   │   ├── projects.py
│   │   ├── suites.py
│   │   ├── testcases.py
│   │   └── executions.py
│   └── mcp_server/
│       ├── __init__.py
│       └── server.py               # MCP tool definitions wrapping services
├── cli/
│   ├── __init__.py
│   └── main.py                     # typer app -> httpx -> REST
├── migrations/                     # alembic
│   ├── env.py
│   └── versions/
└── tests/
    ├── __init__.py
    ├── conftest.py                 # db fixture, client fixture, auth fixtures
    ├── test_auth.py
    ├── test_projects.py
    ├── test_suites.py
    ├── test_testcases.py
    ├── test_executions.py
    ├── test_services.py            # direct service-layer tests
    └── test_mcp.py
```

**Design rationale:**
- **Services are transport-agnostic.** They accept primitives / Pydantic models and an `AsyncSession`, raise domain errors from `services/errors.py`, and never import FastAPI. This is what lets the MCP server reuse them without an HTTP round-trip.
- **Models split by domain**, all imported in `models/__init__.py` so Alembic autogenerate sees them.
- **One migration creates the full schema** even though only some tables are used in Phase 1.

---

## Task 0: Project Scaffolding & Tooling

**Files:**
- Create: `pyproject.toml`, `.env.example`, `docker-compose.yml`, `Dockerfile`, `app/__init__.py`, `app/config.py`, `.gitignore`

- [ ] **Step 1: Initialize git and Python project**

```bash
cd /Users/nt/PycharmProjects/agentqa
git init
python3.12 -m venv .venv
source .venv/bin/activate
```

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "agentqa"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "pydantic>=2.10",
    "pydantic-settings>=2.6",
    "python-jose[cryptography]>=3.3",
    "passlib[bcrypt]>=1.7",
    "pgvector>=0.3.6",
    "mcp>=1.1",
    "typer>=0.13",
    "httpx>=0.28",
    "python-multipart>=0.0.12",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "ruff>=0.8",
]

[project.scripts]
agentqa = "cli.main:app"

[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 3: Install dependencies**

```bash
pip install -e ".[dev]"
```

Expected: installs cleanly, `agentqa` script available.

- [ ] **Step 4: Write `.env.example`**

```bash
# Database
DATABASE_URL=postgresql+asyncpg://agentqa:agentqa@localhost:5432/agentqa
# Auth
JWT_SECRET=change-me-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
# Blob store (MinIO) — used Phase 2+
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=agentqa-artifacts
# API base for the CLI
AGENTQA_API_URL=http://localhost:8000
AGENTQA_API_KEY=
```

Then `cp .env.example .env`.

- [ ] **Step 5: Write `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
.ruff_cache/
*.egg-info/
```

- [ ] **Step 6: Write `app/config.py`**

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://agentqa:agentqa@localhost:5432/agentqa"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "agentqa-artifacts"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Create empty `app/__init__.py`.

- [ ] **Step 7: Write `docker-compose.yml`**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: agentqa
      POSTGRES_PASSWORD: agentqa
      POSTGRES_DB: agentqa
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agentqa"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - miniodata:/data

  api:
    build: .
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://agentqa:agentqa@postgres:5432/agentqa
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

volumes:
  pgdata:
  miniodata:
```

- [ ] **Step 8: Write `Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /code
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 9: Start the database and verify**

```bash
docker compose up -d postgres
docker compose exec postgres pg_isready -U agentqa
```

Expected: `accepting connections`.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "chore: project scaffolding, deps, docker-compose"
```

---

## Task 1: Database Layer & Base Model

**Files:**
- Create: `app/db.py`, `app/models/__init__.py`, `app/models/base.py`
- Test: `tests/conftest.py`, `tests/test_services.py`

- [ ] **Step 1: Write `app/models/base.py`**

```python
import datetime as dt

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
```

- [ ] **Step 2: Write `app/db.py`**

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

_settings = get_settings()
engine = create_async_engine(_settings.database_url, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 3: Write `app/models/__init__.py` (stub — models added per task)**

```python
from app.models.base import Base

__all__ = ["Base"]
```

- [ ] **Step 4: Write `tests/conftest.py`**

This creates a fresh schema per test session against the running Postgres, using a separate test database name.

```python
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
```

- [ ] **Step 5: Write a smoke test in `tests/test_services.py`**

```python
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_db_connection(session):
    result = await session.execute(text("SELECT 1"))
    assert result.scalar() == 1
```

- [ ] **Step 6: Run the smoke test**

Run: `pytest tests/test_services.py::test_db_connection -v`
Expected: PASS (confirms test DB creation + connection works).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: async db layer, base model, test harness"
```

---

## Task 2: ORM Models & Full Schema Migration

This task defines all ORM models then generates one Alembic migration creating the full schema. Models for later phases are defined now so the schema is complete; only Phase-1 models get services.

**Files:**
- Create: `app/models/structure.py`, `app/models/user.py`, `app/models/testcase.py`, `app/models/plan.py`, `app/models/execution.py`, `app/models/evidence.py`, `app/models/requirement.py`, `app/models/meta.py`
- Modify: `app/models/__init__.py`
- Create: `alembic.ini`, `migrations/env.py`, first migration in `migrations/versions/`
- Test: `tests/test_services.py`

- [ ] **Step 1: Write `app/models/user.py`**

```python
import datetime as dt

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Role(Base, TimestampMixin):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str | None] = mapped_column(Text)


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(String(128), unique=True)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id"), primary_key=True)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(256))
    email: Mapped[str | None] = mapped_column(String(256))
    first: Mapped[str | None] = mapped_column(String(128))
    last: Mapped[str | None] = mapped_column(String(128))
    role_id: Mapped[int | None] = mapped_column(ForeignKey("roles.id"))
    api_key: Mapped[str | None] = mapped_column(String(128), unique=True, index=True)
    auth_method: Mapped[str] = mapped_column(String(16), default="db")  # db|ldap|oauth|agent
    agent_model: Mapped[str | None] = mapped_column(String(128))
    notification_config: Mapped[dict | None] = mapped_column(JSONB)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class UserProjectRole(Base):
    __tablename__ = "user_project_roles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))


class UserPlanRole(Base):
    __tablename__ = "user_plan_roles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("test_plans.id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))


class Assignment(Base, TimestampMixin):
    __tablename__ = "assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str | None] = mapped_column(String(32))
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"))
    plan_id: Mapped[int] = mapped_column(ForeignKey("test_plans.id"))
    build_id: Mapped[int | None] = mapped_column(ForeignKey("builds.id"))
    assignee_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assignee_type: Mapped[str] = mapped_column(String(16))  # human|agent
    deadline: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="open")
    assigner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
```

- [ ] **Step 2: Write `app/models/structure.py`**

```python
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    prefix: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    options: Mapped[dict | None] = mapped_column(JSONB)
    api_key: Mapped[str | None] = mapped_column(String(128))
    tc_counter: Mapped[int] = mapped_column(Integer, default=0)  # for external_id generation

    suites: Mapped[list["TestSuite"]] = relationship(back_populates="project")


class TestSuite(Base, TimestampMixin):
    __tablename__ = "test_suites"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("test_suites.id"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    details: Mapped[str | None] = mapped_column(Text)
    order: Mapped[int] = mapped_column(Integer, default=0)

    project: Mapped["Project"] = relationship(back_populates="suites")


class Keyword(Base):
    __tablename__ = "keywords"
    __table_args__ = (UniqueConstraint("project_id", "keyword"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    keyword: Mapped[str] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)


class Platform(Base):
    __tablename__ = "platforms"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 3: Write `app/models/testcase.py`**

```python
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TestCase(Base, TimestampMixin):
    __tablename__ = "test_cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    suite_id: Mapped[int] = mapped_column(ForeignKey("test_suites.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(64), index=True)  # e.g. "PROJ-42"
    name: Mapped[str] = mapped_column(String(256))

    versions: Mapped[list["TestCaseVersion"]] = relationship(
        back_populates="case", order_by="TestCaseVersion.version"
    )


class TestCaseVersion(Base, TimestampMixin):
    __tablename__ = "test_case_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    summary: Mapped[str | None] = mapped_column(Text)
    preconditions: Mapped[str | None] = mapped_column(Text)
    importance: Mapped[int] = mapped_column(Integer, default=2)  # 1 low,2 med,3 high
    execution_type: Mapped[str] = mapped_column(String(16), default="manual")  # manual|automated
    status: Mapped[str] = mapped_column(String(16), default="draft")
    estimated_duration: Mapped[int | None] = mapped_column(Integer)  # seconds
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    case: Mapped["TestCase"] = relationship(back_populates="versions")
    steps: Mapped[list["TestStep"]] = relationship(
        back_populates="version", order_by="TestStep.step_number", cascade="all, delete-orphan"
    )


class TestStep(Base):
    __tablename__ = "test_steps"
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("test_case_versions.id"), index=True)
    step_number: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(Text)
    expected_result: Mapped[str | None] = mapped_column(Text)
    execution_type: Mapped[str] = mapped_column(String(16), default="manual")

    version: Mapped["TestCaseVersion"] = relationship(back_populates="steps")


class TestCaseRelation(Base, TimestampMixin):
    __tablename__ = "test_case_relations"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"))
    dest_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"))
    relation_type: Mapped[str] = mapped_column(String(32))  # blocks|duplicates|relates


class TestCaseScriptLink(Base):
    __tablename__ = "test_case_script_links"
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("test_case_versions.id"), index=True)
    repo: Mapped[str] = mapped_column(String(256))
    branch: Mapped[str | None] = mapped_column(String(128))
    path: Mapped[str] = mapped_column(String(512))
    commit_id: Mapped[str | None] = mapped_column(String(64))
```

- [ ] **Step 4: Write `app/models/plan.py`** (created now, services deferred to Phase 2)

```python
import datetime as dt

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class TestPlan(Base, TimestampMixin):
    __tablename__ = "test_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)


class TestPlanCase(Base):
    __tablename__ = "test_plan_cases"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("test_plans.id"), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("test_case_versions.id"))
    platform_id: Mapped[int | None] = mapped_column(ForeignKey("platforms.id"))
    order: Mapped[int] = mapped_column(Integer, default=0)
    urgency: Mapped[int] = mapped_column(Integer, default=2)


class TestPlanPlatform(Base):
    __tablename__ = "test_plan_platforms"
    plan_id: Mapped[int] = mapped_column(ForeignKey("test_plans.id"), primary_key=True)
    platform_id: Mapped[int] = mapped_column(ForeignKey("platforms.id"), primary_key=True)


class Build(Base, TimestampMixin):
    __tablename__ = "builds"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("test_plans.id"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    tag: Mapped[str | None] = mapped_column(String(128))
    branch: Mapped[str | None] = mapped_column(String(128))
    commit_id: Mapped[str | None] = mapped_column(String(64))
    release_date: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class Milestone(Base):
    __tablename__ = "milestones"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("test_plans.id"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    target_date: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    start_date: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("test_plans.id"), index=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"))
    risk: Mapped[str | None] = mapped_column(String(8))
    importance: Mapped[str | None] = mapped_column(String(8))
```

- [ ] **Step 5: Write `app/models/execution.py`**

```python
import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Execution(Base):
    __tablename__ = "executions"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("test_plans.id"), index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("test_case_versions.id"), index=True)
    build_id: Mapped[int | None] = mapped_column(ForeignKey("builds.id"), index=True)
    platform_id: Mapped[int | None] = mapped_column(ForeignKey("platforms.id"))
    tester_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    execution_type: Mapped[str] = mapped_column(String(16), default="manual")
    status: Mapped[str] = mapped_column(String(16))  # pass|fail|blocked|not_run|in_progress
    duration: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    session_id: Mapped[str | None] = mapped_column(String(128))
    run_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    steps: Mapped[list["ExecutionStep"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan"
    )


class ExecutionStep(Base):
    __tablename__ = "execution_steps"
    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("executions.id"), index=True)
    step_id: Mapped[int] = mapped_column(ForeignKey("test_steps.id"))
    status: Mapped[str] = mapped_column(String(16))
    notes: Mapped[str | None] = mapped_column(Text)

    execution: Mapped["Execution"] = relationship(back_populates="steps")


class ExecutionBug(Base):
    __tablename__ = "execution_bugs"
    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("executions.id"), index=True)
    step_id: Mapped[int | None] = mapped_column(ForeignKey("test_steps.id"))
    bug_id: Mapped[str] = mapped_column(String(128))  # external tracker ref
```

- [ ] **Step 6: Write `app/models/evidence.py`** (created now, services in Phase 2)

```python
import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExecutionArtifact(Base):
    __tablename__ = "execution_artifacts"
    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("executions.id"), index=True)
    artifact_type: Mapped[str] = mapped_column(String(32))  # trace|log|screenshot|dump|network|tool_calls
    title: Mapped[str | None] = mapped_column(String(256))
    blob_key: Mapped[str] = mapped_column(String(512))
    size: Mapped[int | None] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(128))


class ExecutionClaim(Base):
    __tablename__ = "execution_claims"
    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("executions.id"), index=True)
    claim_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ClaimVerification(Base):
    __tablename__ = "claim_verifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    claim_id: Mapped[int] = mapped_column(ForeignKey("execution_claims.id"), index=True)
    auditor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    verdict: Mapped[str] = mapped_column(String(16))  # confirmed|refuted|inconclusive
    reasoning: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ExecutionReasoning(Base):
    __tablename__ = "execution_reasoning"
    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("executions.id"), index=True)
    reasoning: Mapped[dict | None] = mapped_column(JSONB)
    agent_model: Mapped[str | None] = mapped_column(String(128))
    agent_session_id: Mapped[str | None] = mapped_column(String(128))
    token_count: Mapped[int | None] = mapped_column(Integer)
    # NOTE: embedding column (pgvector) added in Phase 2 migration


class AuditReport(Base):
    __tablename__ = "audit_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32))  # case_version|suite|plan
    entity_id: Mapped[int] = mapped_column(Integer)
    auditor_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    findings: Mapped[dict | None] = mapped_column(JSONB)
    quality_score: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 7: Write `app/models/requirement.py`** (created now, services in Phase 2)

```python
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ReqSpec(Base, TimestampMixin):
    __tablename__ = "req_specs"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    doc_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(256))
    scope: Mapped[str | None] = mapped_column(Text)


class Requirement(Base, TimestampMixin):
    __tablename__ = "requirements"
    id: Mapped[int] = mapped_column(primary_key=True)
    spec_id: Mapped[int] = mapped_column(ForeignKey("req_specs.id"), index=True)
    req_doc_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(256))


class ReqVersion(Base):
    __tablename__ = "req_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    req_id: Mapped[int] = mapped_column(ForeignKey("requirements.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    scope: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(32))
    type: Mapped[str | None] = mapped_column(String(32))
    expected_coverage: Mapped[int | None] = mapped_column(Integer)


class ReqCoverage(Base):
    __tablename__ = "req_coverage"
    id: Mapped[int] = mapped_column(primary_key=True)
    req_version_id: Mapped[int] = mapped_column(ForeignKey("req_versions.id"), index=True)
    case_version_id: Mapped[int] = mapped_column(ForeignKey("test_case_versions.id"), index=True)
    link_status: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ReqRelation(Base):
    __tablename__ = "req_relations"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("requirements.id"))
    dest_id: Mapped[int] = mapped_column(ForeignKey("requirements.id"))
    relation_type: Mapped[str] = mapped_column(String(32))
```

- [ ] **Step 8: Write `app/models/meta.py`** (created now, services in Phase 2+)

```python
from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class CustomField(Base):
    __tablename__ = "custom_fields"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    label: Mapped[str] = mapped_column(String(256))
    type: Mapped[str] = mapped_column(String(32))
    possible_values: Mapped[str | None] = mapped_column(Text)
    valid_regexp: Mapped[str | None] = mapped_column(String(256))
    show_on_design: Mapped[bool] = mapped_column(Boolean, default=True)
    show_on_execution: Mapped[bool] = mapped_column(Boolean, default=False)


class CustomFieldValue(Base):
    __tablename__ = "custom_field_values"
    id: Mapped[int] = mapped_column(primary_key=True)
    field_id: Mapped[int] = mapped_column(ForeignKey("custom_fields.id"), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    value: Mapped[str | None] = mapped_column(Text)


class Attachment(Base, TimestampMixin):
    __tablename__ = "attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str | None] = mapped_column(String(256))
    blob_key: Mapped[str] = mapped_column(String(512))
    file_name: Mapped[str | None] = mapped_column(String(256))
    size: Mapped[int | None] = mapped_column(Integer)
    mime_type: Mapped[str | None] = mapped_column(String(128))


class TestCaseKeyword(Base):
    __tablename__ = "test_case_keywords"
    case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), primary_key=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id"), primary_key=True)


class Inventory(Base, TimestampMixin):
    __tablename__ = "inventory"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(256))
    ip_address: Mapped[str | None] = mapped_column(String(64))
    content: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class TextTemplate(Base, TimestampMixin):
    __tablename__ = "text_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(256))
    content: Mapped[str | None] = mapped_column(Text)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))


class IssueTracker(Base):
    __tablename__ = "issue_trackers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    type: Mapped[str] = mapped_column(String(32))
    config: Mapped[dict | None] = mapped_column(JSONB)


class CodeTracker(Base):
    __tablename__ = "code_trackers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    type: Mapped[str] = mapped_column(String(32))
    config: Mapped[dict | None] = mapped_column(JSONB)


class ReqMgrSystem(Base):
    __tablename__ = "req_mgr_systems"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    type: Mapped[str] = mapped_column(String(32))
    config: Mapped[dict | None] = mapped_column(JSONB)


class ProjectIntegration(Base):
    __tablename__ = "project_integrations"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    tracker_id: Mapped[int] = mapped_column(Integer)
    tracker_type: Mapped[str] = mapped_column(String(32))


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    activity: Mapped[str] = mapped_column(String(64))
    object_type: Mapped[str | None] = mapped_column(String(32))
    object_id: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    fired_at: Mapped[str | None] = mapped_column(String(64))


class Plugin(Base):
    __tablename__ = "plugins"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict | None] = mapped_column(JSONB)
```

- [ ] **Step 9: Update `app/models/__init__.py` to import everything**

```python
from app.models.base import Base
from app.models.structure import Keyword, Platform, Project, TestSuite
from app.models.user import (
    Assignment,
    Permission,
    Role,
    RolePermission,
    User,
    UserPlanRole,
    UserProjectRole,
)
from app.models.testcase import (
    TestCase,
    TestCaseRelation,
    TestCaseScriptLink,
    TestCaseVersion,
    TestStep,
)
from app.models.plan import (
    Build,
    Milestone,
    RiskAssessment,
    TestPlan,
    TestPlanCase,
    TestPlanPlatform,
)
from app.models.execution import Execution, ExecutionBug, ExecutionStep
from app.models.evidence import (
    AuditReport,
    ClaimVerification,
    ExecutionArtifact,
    ExecutionClaim,
    ExecutionReasoning,
)
from app.models.requirement import (
    ReqCoverage,
    ReqRelation,
    ReqSpec,
    ReqVersion,
    Requirement,
)
from app.models.meta import (
    Attachment,
    AuditEvent,
    CodeTracker,
    CustomField,
    CustomFieldValue,
    Inventory,
    IssueTracker,
    Plugin,
    ProjectIntegration,
    ReqMgrSystem,
    TestCaseKeyword,
    TextTemplate,
)

__all__ = ["Base"]  # plus all models above, registered on Base.metadata
```

- [ ] **Step 10: Write a model-registration test in `tests/test_services.py` (append)**

```python
def test_all_tables_registered():
    from app.models.base import Base

    names = set(Base.metadata.tables.keys())
    expected = {
        "projects", "test_suites", "keywords", "platforms",
        "test_cases", "test_case_versions", "test_steps",
        "executions", "execution_steps",
        "users", "roles", "assignments",
        "test_plans", "builds",
        "execution_claims", "claim_verifications",
        "req_specs", "requirements",
    }
    missing = expected - names
    assert not missing, f"missing tables: {missing}"
```

- [ ] **Step 11: Run model tests**

Run: `pytest tests/test_services.py -v`
Expected: PASS — confirms all models import and register, and `Base.metadata.create_all` works in the `engine` fixture.

- [ ] **Step 12: Initialize Alembic**

```bash
alembic init -t async migrations
```

- [ ] **Step 13: Edit `alembic.ini`** — set the URL line to a placeholder (real URL injected in env.py):

```ini
sqlalchemy.url =
```

- [ ] **Step 14: Replace `migrations/env.py` target metadata + URL wiring**

Replace the relevant parts so Alembic uses our settings and metadata:

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
from alembic import context

import app.models  # noqa: F401  registers all tables
from app.models.base import Base
from app.config import get_settings

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online():
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    raise RuntimeError("offline mode not supported")
else:
    run_migrations_online()
```

- [ ] **Step 15: Add pgvector extension to the first migration manually**

First autogenerate:

```bash
docker compose up -d postgres
alembic revision --autogenerate -m "initial schema"
```

Then open the generated file in `migrations/versions/` and add, at the very top of `upgrade()`:

```python
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
```

(The `vector` type isn't used by any column yet — Phase 2 adds the embedding column — but enabling the extension now keeps the Phase-2 migration non-privileged.)

- [ ] **Step 16: Apply the migration**

Run: `alembic upgrade head`
Expected: all tables created in the `agentqa` database, no errors.

- [ ] **Step 17: Verify schema**

```bash
docker compose exec postgres psql -U agentqa -c "\dt"
```

Expected: lists ~35 tables including `projects`, `test_cases`, `executions`, `alembic_version`.

- [ ] **Step 18: Commit**

```bash
git add -A
git commit -m "feat: full ORM schema + initial alembic migration with pgvector"
```

---

## Task 3: Domain Errors & Auth Service

The auth service owns password hashing, JWT creation/decoding, API-key generation, and user lookup. It is transport-agnostic.

**Files:**
- Create: `app/services/__init__.py`, `app/services/errors.py`, `app/services/auth.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write `app/services/errors.py`**

```python
class ServiceError(Exception):
    """Base for all domain errors. Routers map these to HTTP codes."""


class NotFound(ServiceError):
    pass


class Conflict(ServiceError):
    pass


class Unauthorized(ServiceError):
    pass


class Forbidden(ServiceError):
    pass


class ValidationFailed(ServiceError):
    pass
```

Create empty `app/services/__init__.py`.

- [ ] **Step 2: Write the failing test `tests/test_auth.py`**

```python
import pytest

from app.services import auth
from app.services.errors import Unauthorized


def test_hash_and_verify_password():
    h = auth.hash_password("hunter2")
    assert h != "hunter2"
    assert auth.verify_password("hunter2", h) is True
    assert auth.verify_password("wrong", h) is False


def test_jwt_roundtrip():
    token = auth.create_access_token(user_id=42)
    assert auth.decode_token(token) == 42


def test_decode_invalid_token_raises():
    with pytest.raises(Unauthorized):
        auth.decode_token("not.a.jwt")


def test_generate_api_key_is_unique_and_prefixed():
    k1 = auth.generate_api_key()
    k2 = auth.generate_api_key()
    assert k1.startswith("aqa_")
    assert k1 != k2
```

- [ ] **Step 3: Run it — verify failure**

Run: `pytest tests/test_auth.py -v`
Expected: FAIL — `app.services.auth` has no such functions yet.

- [ ] **Step 4: Write `app/services/auth.py`**

```python
import datetime as dt
import secrets

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.services.errors import Unauthorized

_settings = get_settings()
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd.verify(plain, hashed)


def create_access_token(user_id: int) -> str:
    expire = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=_settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, _settings.jwt_secret, algorithm=_settings.jwt_algorithm)


def decode_token(token: str) -> int:
    try:
        payload = jwt.decode(token, _settings.jwt_secret, algorithms=[_settings.jwt_algorithm])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError) as e:
        raise Unauthorized("invalid token") from e


def generate_api_key() -> str:
    return "aqa_" + secrets.token_urlsafe(32)


async def authenticate_user(session: AsyncSession, login: str, password: str) -> User:
    user = (await session.execute(select(User).where(User.login == login))).scalar_one_or_none()
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        raise Unauthorized("bad credentials")
    if not user.active:
        raise Unauthorized("inactive user")
    return user


async def user_from_token(session: AsyncSession, token: str) -> User:
    user_id = decode_token(token)
    user = await session.get(User, user_id)
    if user is None or not user.active:
        raise Unauthorized("user not found")
    return user


async def user_from_api_key(session: AsyncSession, api_key: str) -> User:
    user = (
        await session.execute(select(User).where(User.api_key == api_key))
    ).scalar_one_or_none()
    if user is None or not user.active:
        raise Unauthorized("invalid api key")
    return user
```

- [ ] **Step 5: Run it — verify pass**

Run: `pytest tests/test_auth.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: domain errors + auth service (hashing, jwt, api keys)"
```

---

## Task 4: FastAPI App, Auth Dependencies & Auth Endpoints

Wires the app factory, the error→HTTP mapping, the auth dependencies (`current_user` accepting either a Bearer JWT or an `X-API-Key`), and `/auth/login` + `/auth/token`.

**Files:**
- Create: `app/main.py`, `app/api/__init__.py`, `app/api/deps.py`, `app/api/auth.py`, `app/schemas/__init__.py`, `app/schemas/auth.py`
- Test: `tests/test_auth.py` (append integration tests), `tests/conftest.py` (append client + user fixtures)

- [ ] **Step 1: Write `app/schemas/auth.py`**

```python
from pydantic import BaseModel


class LoginRequest(BaseModel):
    login: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ApiKeyResponse(BaseModel):
    api_key: str


class UserOut(BaseModel):
    id: int
    login: str
    email: str | None = None
    auth_method: str
    active: bool

    model_config = {"from_attributes": True}
```

Create empty `app/schemas/__init__.py`.

- [ ] **Step 2: Write `app/api/deps.py`**

```python
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.user import User
from app.services import auth
from app.services.errors import Unauthorized

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header()] = None,
) -> User:
    try:
        if x_api_key:
            return await auth.user_from_api_key(session, x_api_key)
        if authorization and authorization.lower().startswith("bearer "):
            return await auth.user_from_token(session, authorization.split(" ", 1)[1])
    except Unauthorized as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    raise HTTPException(status_code=401, detail="missing credentials")


CurrentUser = Annotated[User, Depends(get_current_user)]
```

- [ ] **Step 3: Write `app/api/auth.py`**

```python
from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.schemas.auth import ApiKeyResponse, LoginRequest, TokenResponse, UserOut
from app.services import auth
from app.services.errors import Unauthorized

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: SessionDep):
    try:
        user = await auth.authenticate_user(session, body.login, body.password)
    except Unauthorized as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    return TokenResponse(access_token=auth.create_access_token(user.id))


@router.post("/token", response_model=ApiKeyResponse)
async def issue_api_key(session: SessionDep, user: CurrentUser):
    user.api_key = auth.generate_api_key()
    await session.commit()
    return ApiKeyResponse(api_key=user.api_key)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user
```

- [ ] **Step 4: Write `app/main.py`**

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.services.errors import (
    Conflict,
    Forbidden,
    NotFound,
    Unauthorized,
    ValidationFailed,
)

_ERROR_STATUS = {
    NotFound: 404,
    Conflict: 409,
    Unauthorized: 401,
    Forbidden: 403,
    ValidationFailed: 422,
}


def create_app() -> FastAPI:
    app = FastAPI(title="AgentQA", version="0.1.0")

    @app.exception_handler(NotFound)
    @app.exception_handler(Conflict)
    @app.exception_handler(Unauthorized)
    @app.exception_handler(Forbidden)
    @app.exception_handler(ValidationFailed)
    async def _service_error_handler(request: Request, exc: Exception):
        status = _ERROR_STATUS.get(type(exc), 400)
        return JSONResponse(status_code=status, content={"detail": str(exc)})

    from app.api import auth, executions, projects, suites, testcases

    app.include_router(auth.router)
    app.include_router(projects.router)
    app.include_router(suites.router)
    app.include_router(testcases.router)
    app.include_router(executions.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()
```

Create empty `app/api/__init__.py`. (Note: `projects`, `suites`, `testcases`, `executions` routers are created in later tasks — to run Task 4 in isolation, temporarily comment their imports/includes, then re-enable as each task lands. The integration test below only needs auth + health.)

- [ ] **Step 5: Append fixtures to `tests/conftest.py`**

```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import get_session
from app.main import create_app
from app.models.user import User
from app.services import auth as auth_service


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
    return u


@pytest_asyncio.fixture
async def auth_headers(client, user) -> dict:
    resp = await client.post("/api/v1/auth/login", json={"login": "alice", "password": "pw"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 6: Append integration tests to `tests/test_auth.py`**

```python
import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_login_success(client, user):
    resp = await client.post("/api/v1/auth/login", json={"login": "alice", "password": "pw"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_bad_password(client, user):
    resp = await client.post("/api/v1/auth/login", json={"login": "alice", "password": "nope"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_with_token(client, auth_headers):
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["login"] == "alice"


@pytest.mark.asyncio
async def test_api_key_issue_and_use(client, auth_headers):
    issued = await client.post("/api/v1/auth/token", headers=auth_headers)
    assert issued.status_code == 200
    key = issued.json()["api_key"]
    assert key.startswith("aqa_")
    resp = await client.get("/api/v1/auth/me", headers={"X-API-Key": key})
    assert resp.status_code == 200
    assert resp.json()["login"] == "alice"
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_auth.py -v`
Expected: PASS (all unit + integration tests). If router imports for unbuilt tasks fail, comment them out in `app/main.py` per the note in Step 4.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: fastapi app factory, auth deps (jwt + api key), auth endpoints"
```

---

## Task 5: Projects — Service + Endpoints

**Files:**
- Create: `app/services/projects.py`, `app/schemas/project.py`, `app/api/projects.py`
- Test: `tests/test_projects.py`

- [ ] **Step 1: Write `app/schemas/project.py`**

```python
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    prefix: str
    options: dict | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    active: bool | None = None
    options: dict | None = None


class ProjectOut(BaseModel):
    id: int
    name: str
    prefix: str
    active: bool
    options: dict | None = None

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Write the failing test `tests/test_projects.py`**

```python
import pytest

from app.services import projects
from app.services.errors import Conflict, NotFound
from app.schemas.project import ProjectCreate


@pytest.mark.asyncio
async def test_create_and_get_project(session):
    p = await projects.create_project(session, ProjectCreate(name="Demo", prefix="DEMO"))
    assert p.id is not None
    fetched = await projects.get_project(session, p.id)
    assert fetched.name == "Demo"


@pytest.mark.asyncio
async def test_duplicate_prefix_conflicts(session):
    await projects.create_project(session, ProjectCreate(name="A", prefix="DUP"))
    with pytest.raises(Conflict):
        await projects.create_project(session, ProjectCreate(name="B", prefix="DUP"))


@pytest.mark.asyncio
async def test_get_missing_raises(session):
    with pytest.raises(NotFound):
        await projects.get_project(session, 99999)


@pytest.mark.asyncio
async def test_project_endpoints(client, auth_headers):
    create = await client.post(
        "/api/v1/projects", json={"name": "Web", "prefix": "WEB"}, headers=auth_headers
    )
    assert create.status_code == 201
    pid = create.json()["id"]
    listed = await client.get("/api/v1/projects", headers=auth_headers)
    assert any(p["id"] == pid for p in listed.json())
    got = await client.get(f"/api/v1/projects/{pid}", headers=auth_headers)
    assert got.json()["prefix"] == "WEB"
```

- [ ] **Step 3: Run it — verify failure**

Run: `pytest tests/test_projects.py -v`
Expected: FAIL — module/functions/routes missing.

- [ ] **Step 4: Write `app/services/projects.py`**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.structure import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.errors import Conflict, NotFound


async def create_project(session: AsyncSession, data: ProjectCreate) -> Project:
    existing = (
        await session.execute(select(Project).where(Project.prefix == data.prefix))
    ).scalar_one_or_none()
    if existing:
        raise Conflict(f"project prefix '{data.prefix}' already exists")
    project = Project(name=data.name, prefix=data.prefix, options=data.options)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def get_project(session: AsyncSession, project_id: int) -> Project:
    project = await session.get(Project, project_id)
    if project is None:
        raise NotFound(f"project {project_id} not found")
    return project


async def list_projects(session: AsyncSession, active: bool | None = None) -> list[Project]:
    stmt = select(Project).order_by(Project.id)
    if active is not None:
        stmt = stmt.where(Project.active == active)
    return list((await session.execute(stmt)).scalars().all())


async def update_project(session: AsyncSession, project_id: int, data: ProjectUpdate) -> Project:
    project = await get_project(session, project_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await session.commit()
    await session.refresh(project)
    return project
```

- [ ] **Step 5: Write `app/api/projects.py`**

```python
from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate
from app.services import projects

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create(body: ProjectCreate, session: SessionDep, user: CurrentUser):
    return await projects.create_project(session, body)


@router.get("", response_model=list[ProjectOut])
async def list_all(session: SessionDep, user: CurrentUser, active: bool | None = None):
    return await projects.list_projects(session, active)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_one(project_id: int, session: SessionDep, user: CurrentUser):
    return await projects.get_project(session, project_id)


@router.put("/{project_id}", response_model=ProjectOut)
async def update(project_id: int, body: ProjectUpdate, session: SessionDep, user: CurrentUser):
    return await projects.update_project(session, project_id, body)
```

- [ ] **Step 6: Ensure `app/main.py` includes the projects router** (uncomment if previously commented).

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_projects.py -v`
Expected: PASS (4 tests).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: projects service + crud endpoints"
```

---

## Task 6: Test Suites — Service (tree + path resolution) + Endpoints

The suite service supports the **find-or-create-by-path** behavior the MCP `create_test_suite` tool needs (e.g. `"Auth/Login/OAuth"`), plus a tree fetch.

**Files:**
- Create: `app/services/suites.py`, `app/schemas/suite.py`, `app/api/suites.py`
- Test: `tests/test_suites.py`

- [ ] **Step 1: Write `app/schemas/suite.py`**

```python
from pydantic import BaseModel


class SuiteCreate(BaseModel):
    name: str
    parent_id: int | None = None
    details: str | None = None


class SuiteOut(BaseModel):
    id: int
    project_id: int
    parent_id: int | None
    name: str
    details: str | None = None
    order: int

    model_config = {"from_attributes": True}


class SuiteNode(SuiteOut):
    children: list["SuiteNode"] = []
```

- [ ] **Step 2: Write the failing test `tests/test_suites.py`**

```python
import pytest

from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.services import projects, suites
from app.services.errors import NotFound


@pytest.mark.asyncio
async def test_create_suite(session):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="P1"))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="Auth"))
    assert s.id is not None
    assert s.parent_id is None


@pytest.mark.asyncio
async def test_find_or_create_path_creates_chain(session):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="P2"))
    leaf = await suites.find_or_create_path(session, p.id, "Auth/Login/OAuth")
    assert leaf.name == "OAuth"
    # second call must reuse, not duplicate
    leaf2 = await suites.find_or_create_path(session, p.id, "Auth/Login/OAuth")
    assert leaf2.id == leaf.id
    all_suites = await suites.list_suites(session, p.id)
    names = sorted(s.name for s in all_suites)
    assert names == ["Auth", "Login", "OAuth"]


@pytest.mark.asyncio
async def test_get_tree(session):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix="P3"))
    await suites.find_or_create_path(session, p.id, "A/B")
    tree = await suites.get_tree(session, p.id)
    assert len(tree) == 1
    assert tree[0].name == "A"
    assert tree[0].children[0].name == "B"


@pytest.mark.asyncio
async def test_create_suite_unknown_project_raises(session):
    with pytest.raises(NotFound):
        await suites.create_suite(session, 9999, SuiteCreate(name="X"))


@pytest.mark.asyncio
async def test_suite_endpoints(client, auth_headers, session):
    pc = await client.post(
        "/api/v1/projects", json={"name": "S", "prefix": "SX"}, headers=auth_headers
    )
    pid = pc.json()["id"]
    sc = await client.post(
        f"/api/v1/projects/{pid}/suites", json={"name": "Root"}, headers=auth_headers
    )
    assert sc.status_code == 201
    tree = await client.get(f"/api/v1/suites/{sc.json()['id']}/tree", headers=auth_headers)
    assert tree.status_code == 200
```

- [ ] **Step 3: Run it — verify failure**

Run: `pytest tests/test_suites.py -v`
Expected: FAIL.

- [ ] **Step 4: Write `app/services/suites.py`**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.structure import TestSuite
from app.schemas.suite import SuiteCreate, SuiteNode
from app.services.errors import NotFound
from app.services.projects import get_project


async def create_suite(session: AsyncSession, project_id: int, data: SuiteCreate) -> TestSuite:
    await get_project(session, project_id)  # raises NotFound if absent
    if data.parent_id is not None:
        parent = await session.get(TestSuite, data.parent_id)
        if parent is None or parent.project_id != project_id:
            raise NotFound(f"parent suite {data.parent_id} not found in project")
    suite = TestSuite(
        project_id=project_id, parent_id=data.parent_id, name=data.name, details=data.details
    )
    session.add(suite)
    await session.commit()
    await session.refresh(suite)
    return suite


async def get_suite(session: AsyncSession, suite_id: int) -> TestSuite:
    suite = await session.get(TestSuite, suite_id)
    if suite is None:
        raise NotFound(f"suite {suite_id} not found")
    return suite


async def list_suites(session: AsyncSession, project_id: int) -> list[TestSuite]:
    stmt = select(TestSuite).where(TestSuite.project_id == project_id).order_by(TestSuite.id)
    return list((await session.execute(stmt)).scalars().all())


async def find_or_create_path(
    session: AsyncSession, project_id: int, path: str
) -> TestSuite:
    """Resolve a slash-delimited path, creating any missing suites. Returns the leaf."""
    await get_project(session, project_id)
    parts = [p.strip() for p in path.split("/") if p.strip()]
    if not parts:
        raise NotFound("empty suite path")
    parent_id: int | None = None
    current: TestSuite | None = None
    for name in parts:
        stmt = select(TestSuite).where(
            TestSuite.project_id == project_id,
            TestSuite.parent_id.is_(parent_id) if parent_id is None
            else TestSuite.parent_id == parent_id,
            TestSuite.name == name,
        )
        current = (await session.execute(stmt)).scalar_one_or_none()
        if current is None:
            current = TestSuite(project_id=project_id, parent_id=parent_id, name=name)
            session.add(current)
            await session.flush()
        parent_id = current.id
    await session.commit()
    await session.refresh(current)
    return current


async def get_tree(session: AsyncSession, project_id: int) -> list[SuiteNode]:
    suites = await list_suites(session, project_id)
    nodes: dict[int, SuiteNode] = {
        s.id: SuiteNode.model_validate(s) for s in suites
    }
    roots: list[SuiteNode] = []
    for s in suites:
        node = nodes[s.id]
        if s.parent_id is None:
            roots.append(node)
        else:
            nodes[s.parent_id].children.append(node)
    return roots
```

- [ ] **Step 5: Write `app/api/suites.py`**

```python
from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.suite import SuiteCreate, SuiteNode, SuiteOut
from app.services import suites

router = APIRouter(prefix="/api/v1", tags=["suites"])


@router.post(
    "/projects/{project_id}/suites",
    response_model=SuiteOut,
    status_code=status.HTTP_201_CREATED,
)
async def create(project_id: int, body: SuiteCreate, session: SessionDep, user: CurrentUser):
    return await suites.create_suite(session, project_id, body)


@router.get("/projects/{project_id}/suites", response_model=list[SuiteOut])
async def list_all(project_id: int, session: SessionDep, user: CurrentUser):
    return await suites.list_suites(session, project_id)


@router.get("/suites/{suite_id}", response_model=SuiteOut)
async def get_one(suite_id: int, session: SessionDep, user: CurrentUser):
    return await suites.get_suite(session, suite_id)


@router.get("/suites/{suite_id}/tree", response_model=list[SuiteNode])
async def tree(suite_id: int, session: SessionDep, user: CurrentUser):
    suite = await suites.get_suite(session, suite_id)
    full = await suites.get_tree(session, suite.project_id)
    return [n for n in _collect(full, suite_id)]


def _collect(nodes, suite_id):
    for n in nodes:
        if n.id == suite_id:
            return [n]
        found = _collect(n.children, suite_id)
        if found:
            return found
    return []
```

- [ ] **Step 6: Ensure `app/main.py` includes the suites router.**

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_suites.py -v`
Expected: PASS (5 tests).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: suites service (path resolution, tree) + endpoints"
```

---

## Task 7: Test Cases — Versioned Service + Endpoints

Creating a test case creates `TestCase` + version 1 (`TestCaseVersion`) + its `TestStep` rows, and allocates an `external_id` (`<PREFIX>-<n>`) from the project counter. `create_version` clones the latest version with changes.

**Files:**
- Create: `app/services/testcases.py`, `app/schemas/testcase.py`, `app/api/testcases.py`
- Test: `tests/test_testcases.py`

- [ ] **Step 1: Write `app/schemas/testcase.py`**

```python
from pydantic import BaseModel


class StepIn(BaseModel):
    action: str
    expected_result: str | None = None
    execution_type: str = "manual"


class StepOut(StepIn):
    id: int
    step_number: int

    model_config = {"from_attributes": True}


class TestCaseCreate(BaseModel):
    name: str
    summary: str | None = None
    preconditions: str | None = None
    importance: int = 2
    execution_type: str = "manual"
    estimated_duration: int | None = None
    steps: list[StepIn] = []


class VersionOut(BaseModel):
    id: int
    version: int
    summary: str | None = None
    preconditions: str | None = None
    importance: int
    execution_type: str
    status: str
    active: bool
    steps: list[StepOut] = []

    model_config = {"from_attributes": True}


class TestCaseOut(BaseModel):
    id: int
    project_id: int
    suite_id: int
    external_id: str
    name: str
    current_version: VersionOut | None = None

    model_config = {"from_attributes": True}


class VersionCreate(BaseModel):
    summary: str | None = None
    preconditions: str | None = None
    importance: int | None = None
    execution_type: str | None = None
    steps: list[StepIn] | None = None
```

- [ ] **Step 2: Write the failing test `tests/test_testcases.py`**

```python
import pytest

from app.schemas.project import ProjectCreate
from app.schemas.testcase import StepIn, TestCaseCreate, VersionCreate
from app.services import projects, suites, testcases
from app.services.errors import NotFound


async def _project_and_suite(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    s = await suites.create_suite(session, p.id, __import__(
        "app.schemas.suite", fromlist=["SuiteCreate"]
    ).SuiteCreate(name="Suite"))
    return p, s


@pytest.mark.asyncio
async def test_create_test_case_makes_version_and_steps(session):
    p, s = await _project_and_suite(session, "TC1")
    tc = await testcases.create_test_case(
        session, s.id,
        TestCaseCreate(
            name="Login works",
            summary="user can log in",
            steps=[StepIn(action="enter creds", expected_result="logged in")],
        ),
    )
    assert tc.external_id == "TC1-1"
    full = await testcases.get_test_case(session, tc.id)
    assert full.current_version.version == 1
    assert len(full.current_version.steps) == 1
    assert full.current_version.steps[0].step_number == 1


@pytest.mark.asyncio
async def test_external_id_increments(session):
    p, s = await _project_and_suite(session, "TC2")
    a = await testcases.create_test_case(session, s.id, TestCaseCreate(name="a"))
    b = await testcases.create_test_case(session, s.id, TestCaseCreate(name="b"))
    assert a.external_id == "TC2-1"
    assert b.external_id == "TC2-2"


@pytest.mark.asyncio
async def test_create_version_clones_and_increments(session):
    p, s = await _project_and_suite(session, "TC3")
    tc = await testcases.create_test_case(
        session, s.id,
        TestCaseCreate(name="v", steps=[StepIn(action="a1")]),
    )
    v2 = await testcases.create_version(
        session, tc.id, VersionCreate(summary="updated", steps=[StepIn(action="a2")])
    )
    assert v2.version == 2
    assert v2.summary == "updated"
    full = await testcases.get_test_case(session, tc.id)
    assert full.current_version.version == 2  # latest active version is current


@pytest.mark.asyncio
async def test_get_by_external_id(session):
    p, s = await _project_and_suite(session, "TC4")
    await testcases.create_test_case(session, s.id, TestCaseCreate(name="x"))
    found = await testcases.get_by_external_id(session, p.id, "TC4-1")
    assert found.name == "x"


@pytest.mark.asyncio
async def test_search_test_cases(session):
    p, s = await _project_and_suite(session, "TC5")
    await testcases.create_test_case(session, s.id, TestCaseCreate(name="payment flow"))
    await testcases.create_test_case(session, s.id, TestCaseCreate(name="login flow"))
    results = await testcases.search_test_cases(session, p.id, "payment")
    assert len(results) == 1
    assert results[0].name == "payment flow"


@pytest.mark.asyncio
async def test_endpoints(client, auth_headers):
    pc = await client.post(
        "/api/v1/projects", json={"name": "E", "prefix": "TCE"}, headers=auth_headers
    )
    pid = pc.json()["id"]
    sc = await client.post(
        f"/api/v1/projects/{pid}/suites", json={"name": "S"}, headers=auth_headers
    )
    sid = sc.json()["id"]
    cc = await client.post(
        f"/api/v1/suites/{sid}/cases",
        json={"name": "case", "steps": [{"action": "do", "expected_result": "done"}]},
        headers=auth_headers,
    )
    assert cc.status_code == 201
    cid = cc.json()["id"]
    got = await client.get(f"/api/v1/cases/{cid}", headers=auth_headers)
    assert got.json()["current_version"]["steps"][0]["action"] == "do"
```

- [ ] **Step 3: Run it — verify failure**

Run: `pytest tests/test_testcases.py -v`
Expected: FAIL.

- [ ] **Step 4: Write `app/services/testcases.py`**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.structure import Project, TestSuite
from app.models.testcase import TestCase, TestCaseVersion, TestStep
from app.schemas.testcase import TestCaseCreate, VersionCreate
from app.services.errors import NotFound


async def _load_full(session: AsyncSession, case_id: int) -> TestCase:
    stmt = (
        select(TestCase)
        .where(TestCase.id == case_id)
        .options(selectinload(TestCase.versions).selectinload(TestCaseVersion.steps))
    )
    tc = (await session.execute(stmt)).scalar_one_or_none()
    if tc is None:
        raise NotFound(f"test case {case_id} not found")
    return tc


def _current_version(tc: TestCase) -> TestCaseVersion | None:
    active = [v for v in tc.versions if v.active]
    return max(active, key=lambda v: v.version) if active else None


async def create_test_case(
    session: AsyncSession, suite_id: int, data: TestCaseCreate
) -> TestCase:
    suite = await session.get(TestSuite, suite_id)
    if suite is None:
        raise NotFound(f"suite {suite_id} not found")
    project = await session.get(Project, suite.project_id)
    project.tc_counter += 1
    external_id = f"{project.prefix}-{project.tc_counter}"

    tc = TestCase(
        suite_id=suite_id,
        project_id=project.id,
        external_id=external_id,
        name=data.name,
    )
    session.add(tc)
    await session.flush()

    version = TestCaseVersion(
        case_id=tc.id,
        version=1,
        summary=data.summary,
        preconditions=data.preconditions,
        importance=data.importance,
        execution_type=data.execution_type,
        estimated_duration=data.estimated_duration,
    )
    session.add(version)
    await session.flush()

    for i, step in enumerate(data.steps, start=1):
        session.add(
            TestStep(
                version_id=version.id,
                step_number=i,
                action=step.action,
                expected_result=step.expected_result,
                execution_type=step.execution_type,
            )
        )
    await session.commit()
    return await _load_full(session, tc.id)


async def create_version(
    session: AsyncSession, case_id: int, data: VersionCreate
) -> TestCaseVersion:
    tc = await _load_full(session, case_id)
    latest = _current_version(tc)
    if latest is None:
        raise NotFound(f"test case {case_id} has no active version")

    new_version = TestCaseVersion(
        case_id=case_id,
        version=latest.version + 1,
        summary=data.summary if data.summary is not None else latest.summary,
        preconditions=data.preconditions
        if data.preconditions is not None
        else latest.preconditions,
        importance=data.importance if data.importance is not None else latest.importance,
        execution_type=data.execution_type
        if data.execution_type is not None
        else latest.execution_type,
    )
    session.add(new_version)
    await session.flush()

    source_steps = (
        [
            TestStep(action=s.action, expected_result=s.expected_result,
                     execution_type=s.execution_type)
            for s in data.steps
        ]
        if data.steps is not None
        else [
            TestStep(action=s.action, expected_result=s.expected_result,
                     execution_type=s.execution_type)
            for s in latest.steps
        ]
    )
    for i, s in enumerate(source_steps, start=1):
        s.version_id = new_version.id
        s.step_number = i
        session.add(s)
    await session.commit()
    await session.refresh(new_version)
    return new_version


async def get_test_case(session: AsyncSession, case_id: int):
    tc = await _load_full(session, case_id)
    from app.schemas.testcase import TestCaseOut, VersionOut

    out = TestCaseOut.model_validate(tc)
    cur = _current_version(tc)
    out.current_version = VersionOut.model_validate(cur) if cur else None
    return out


async def get_by_external_id(session: AsyncSession, project_id: int, external_id: str):
    stmt = select(TestCase).where(
        TestCase.project_id == project_id, TestCase.external_id == external_id
    )
    tc = (await session.execute(stmt)).scalar_one_or_none()
    if tc is None:
        raise NotFound(f"test case '{external_id}' not found")
    return await get_test_case(session, tc.id)


async def search_test_cases(
    session: AsyncSession, project_id: int, query: str
) -> list[TestCase]:
    stmt = select(TestCase).where(
        TestCase.project_id == project_id,
        TestCase.name.ilike(f"%{query}%"),
    ).order_by(TestCase.id)
    return list((await session.execute(stmt)).scalars().all())
```

- [ ] **Step 5: Write `app/api/testcases.py`**

```python
from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.testcase import TestCaseCreate, TestCaseOut, VersionCreate, VersionOut
from app.services import suites, testcases

router = APIRouter(prefix="/api/v1", tags=["testcases"])


@router.post(
    "/suites/{suite_id}/cases", response_model=TestCaseOut, status_code=status.HTTP_201_CREATED
)
async def create(suite_id: int, body: TestCaseCreate, session: SessionDep, user: CurrentUser):
    tc = await testcases.create_test_case(session, suite_id, body)
    return await testcases.get_test_case(session, tc.id)


@router.get("/cases/{case_id}", response_model=TestCaseOut)
async def get_one(case_id: int, session: SessionDep, user: CurrentUser):
    return await testcases.get_test_case(session, case_id)


@router.post("/cases/{case_id}/versions", response_model=VersionOut)
async def new_version(case_id: int, body: VersionCreate, session: SessionDep, user: CurrentUser):
    return await testcases.create_version(session, case_id, body)
```

- [ ] **Step 6: Ensure `app/main.py` includes the testcases router.**

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_testcases.py -v`
Expected: PASS (6 tests).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: versioned test cases service + endpoints with external_id allocation"
```

---

## Task 8: Executions — Recording with Build Upsert

`record_execution` is the hot path. It accepts a case (by id or external_id), a plan, a `build_name` (+ optional `commit_id`), and upserts the build (find-or-create on `plan_id` + `name`). It records against the case's **current version** and writes per-step results.

**Files:**
- Create: `app/services/executions.py`, `app/schemas/execution.py`, `app/api/executions.py`
- Test: `tests/test_executions.py`

- [ ] **Step 1: Write `app/schemas/execution.py`**

```python
import datetime as dt

from pydantic import BaseModel


class StepResultIn(BaseModel):
    step_number: int
    status: str  # pass|fail|blocked|not_run
    notes: str | None = None


class ExecutionCreate(BaseModel):
    case_id: int | None = None
    external_id: str | None = None
    project_id: int | None = None  # required if external_id is used
    plan_id: int | None = None
    build_name: str
    commit_id: str | None = None
    status: str  # pass|fail|blocked|not_run|in_progress
    step_results: list[StepResultIn] = []
    notes: str | None = None
    duration: int | None = None
    session_id: str | None = None
    run_id: str | None = None


class ExecutionStepOut(BaseModel):
    step_id: int
    status: str
    notes: str | None = None

    model_config = {"from_attributes": True}


class ExecutionOut(BaseModel):
    id: int
    version_id: int
    build_id: int | None
    plan_id: int | None
    tester_id: int | None
    status: str
    notes: str | None = None
    duration: int | None = None
    session_id: str | None = None
    run_id: str | None = None
    created_at: dt.datetime
    steps: list[ExecutionStepOut] = []

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Write the failing test `tests/test_executions.py`**

```python
import pytest

from app.schemas.execution import ExecutionCreate, StepResultIn
from app.schemas.project import ProjectCreate
from app.schemas.suite import SuiteCreate
from app.schemas.testcase import StepIn, TestCaseCreate
from app.models.plan import TestPlan
from app.services import executions, projects, suites, testcases
from app.services.errors import NotFound


async def _fixture(session, prefix):
    p = await projects.create_project(session, ProjectCreate(name="P", prefix=prefix))
    s = await suites.create_suite(session, p.id, SuiteCreate(name="S"))
    tc = await testcases.create_test_case(
        session, s.id,
        TestCaseCreate(name="c", steps=[StepIn(action="a1"), StepIn(action="a2")]),
    )
    plan = TestPlan(project_id=p.id, name="Plan")
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return p, s, tc, plan


@pytest.mark.asyncio
async def test_record_execution_upserts_build(session):
    p, s, tc, plan = await _fixture(session, "EX1")
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id, plan_id=plan.id, build_name="build-42",
            commit_id="abc123", status="pass",
        ),
        tester_id=None,
    )
    assert ex.build_id is not None
    # second run with same build_name reuses the build
    ex2 = await executions.record_execution(
        session,
        ExecutionCreate(case_id=tc.id, plan_id=plan.id, build_name="build-42", status="fail"),
        tester_id=None,
    )
    assert ex2.build_id == ex.build_id


@pytest.mark.asyncio
async def test_record_with_step_results(session):
    p, s, tc, plan = await _fixture(session, "EX2")
    full = await testcases.get_test_case(session, tc.id)
    steps = full.current_version.steps
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            case_id=tc.id, plan_id=plan.id, build_name="b", status="fail",
            step_results=[
                StepResultIn(step_number=1, status="pass"),
                StepResultIn(step_number=2, status="fail", notes="boom"),
            ],
        ),
        tester_id=None,
    )
    assert len(ex.steps) == 2


@pytest.mark.asyncio
async def test_record_by_external_id(session):
    p, s, tc, plan = await _fixture(session, "EX3")
    ex = await executions.record_execution(
        session,
        ExecutionCreate(
            external_id="EX3-1", project_id=p.id, plan_id=plan.id,
            build_name="b", status="pass",
        ),
        tester_id=None,
    )
    assert ex.id is not None


@pytest.mark.asyncio
async def test_record_unknown_case_raises(session):
    p, s, tc, plan = await _fixture(session, "EX4")
    with pytest.raises(NotFound):
        await executions.record_execution(
            session,
            ExecutionCreate(case_id=99999, plan_id=plan.id, build_name="b", status="pass"),
            tester_id=None,
        )


@pytest.mark.asyncio
async def test_list_executions_for_case(session):
    p, s, tc, plan = await _fixture(session, "EX5")
    await executions.record_execution(
        session,
        ExecutionCreate(case_id=tc.id, plan_id=plan.id, build_name="b", status="pass"),
        tester_id=None,
    )
    rows = await executions.list_for_case(session, tc.id)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_execution_endpoint(client, auth_headers, session):
    pc = await client.post(
        "/api/v1/projects", json={"name": "E", "prefix": "EXE"}, headers=auth_headers
    )
    pid = pc.json()["id"]
    sc = await client.post(
        f"/api/v1/projects/{pid}/suites", json={"name": "S"}, headers=auth_headers
    )
    cc = await client.post(
        f"/api/v1/suites/{sc.json()['id']}/cases", json={"name": "c"}, headers=auth_headers
    )
    plan = TestPlan(project_id=pid, name="P")
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    resp = await client.post(
        "/api/v1/executions",
        json={"case_id": cc.json()["id"], "plan_id": plan.id,
              "build_name": "b1", "status": "pass"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pass"
```

- [ ] **Step 3: Run it — verify failure**

Run: `pytest tests/test_executions.py -v`
Expected: FAIL.

- [ ] **Step 4: Write `app/services/executions.py`**

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.execution import Execution, ExecutionStep
from app.models.plan import Build, TestPlan
from app.models.testcase import TestCase, TestCaseVersion, TestStep
from app.schemas.execution import ExecutionCreate
from app.services.errors import NotFound, ValidationFailed


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
        # map step_number -> test_step.id for this version
        steps = (
            await session.execute(
                select(TestStep).where(TestStep.version_id == version_id)
            )
        ).scalars().all()
        by_number = {s.step_number: s.id for s in steps}
        for sr in data.step_results:
            step_id = by_number.get(sr.step_number)
            if step_id is None:
                raise ValidationFailed(f"step_number {sr.step_number} not in current version")
            session.add(
                ExecutionStep(
                    execution_id=execution.id, step_id=step_id,
                    status=sr.status, notes=sr.notes,
                )
            )
    await session.commit()
    return await _load(session, execution.id)


async def _load(session: AsyncSession, execution_id: int) -> Execution:
    stmt = (
        select(Execution)
        .where(Execution.id == execution_id)
        .options(selectinload(Execution.steps))
    )
    ex = (await session.execute(stmt)).scalar_one_or_none()
    if ex is None:
        raise NotFound(f"execution {execution_id} not found")
    return ex


async def get_execution(session: AsyncSession, execution_id: int) -> Execution:
    return await _load(session, execution_id)


async def list_for_case(session: AsyncSession, case_id: int) -> list[Execution]:
    version_ids = (
        await session.execute(
            select(TestCaseVersion.id).where(TestCaseVersion.case_id == case_id)
        )
    ).scalars().all()
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
```

- [ ] **Step 5: Write `app/api/executions.py`**

```python
from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.execution import ExecutionCreate, ExecutionOut
from app.services import executions

router = APIRouter(prefix="/api/v1", tags=["executions"])


@router.post("/executions", response_model=ExecutionOut, status_code=status.HTTP_201_CREATED)
async def record(body: ExecutionCreate, session: SessionDep, user: CurrentUser):
    tester_id = None if user.auth_method == "agent" else user.id
    return await executions.record_execution(session, body, tester_id=tester_id)


@router.get("/executions/{execution_id}", response_model=ExecutionOut)
async def get_one(execution_id: int, session: SessionDep, user: CurrentUser):
    return await executions.get_execution(session, execution_id)


@router.get("/cases/{case_id}/executions", response_model=list[ExecutionOut])
async def for_case(case_id: int, session: SessionDep, user: CurrentUser):
    return await executions.list_for_case(session, case_id)


@router.get("/plans/{plan_id}/executions", response_model=list[ExecutionOut])
async def for_plan(plan_id: int, session: SessionDep, user: CurrentUser):
    return await executions.list_for_plan(session, plan_id)
```

- [ ] **Step 6: Ensure `app/main.py` includes the executions router.**

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_executions.py -v`
Expected: PASS (6 tests).

- [ ] **Step 8: Run the FULL suite to confirm nothing regressed**

Run: `pytest -v`
Expected: ALL PASS.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: execution recording with build upsert + per-step results"
```

---

## Task 9: MCP Server — Workflow Tools (Phase-1 subset)

The MCP server wraps the **service layer directly** (no HTTP round-trip), opening its own DB session per call. Phase 1 implements the 6 tools whose entities exist now: `create_test_suite`, `create_test_case`, `bulk_create_test_cases`, `get_test_case`, `search_test_cases`, `record_test_run`. The remaining 13 tools (audit, evidence, requirements, assignments, similarity) are registered as explicit "not yet implemented in Phase 1" stubs so the tool list is complete and later phases just fill in bodies.

**Files:**
- Create: `app/mcp_server/__init__.py`, `app/mcp_server/server.py`
- Test: `tests/test_mcp.py`

- [ ] **Step 1: Write the failing test `tests/test_mcp.py`**

The tools are thin async functions; we test them directly with the test DB session by monkeypatching the session factory the server uses.

```python
import pytest

from app.mcp_server import server as mcp
from app.schemas.project import ProjectCreate
from app.services import projects


@pytest.fixture(autouse=True)
def _use_test_session(session, monkeypatch):
    # server._session() must yield our test session
    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(mcp, "_session", lambda: _Ctx())


@pytest.mark.asyncio
async def test_create_test_suite_by_path(session):
    p = await projects.create_project(session, ProjectCreate(name="M", prefix="MCP"))
    result = await mcp.create_test_suite(project_id=p.id, path="A/B/C")
    assert result["name"] == "C"
    assert result["id"] is not None


@pytest.mark.asyncio
async def test_create_and_get_test_case(session):
    p = await projects.create_project(session, ProjectCreate(name="M2", prefix="MC2"))
    await mcp.create_test_suite(project_id=p.id, path="Root")
    case = await mcp.create_test_case(
        project_id=p.id, suite_path="Root", name="login",
        summary="s", steps=[{"action": "go", "expected_result": "ok"}],
    )
    fetched = await mcp.get_test_case(case_id=case["id"])
    assert fetched["name"] == "login"
    assert fetched["current_version"]["steps"][0]["action"] == "go"


@pytest.mark.asyncio
async def test_bulk_create(session):
    p = await projects.create_project(session, ProjectCreate(name="M3", prefix="MC3"))
    result = await mcp.bulk_create_test_cases(
        project_id=p.id, suite_path="Bulk",
        cases=[{"name": "a"}, {"name": "b"}],
    )
    assert len(result) == 2


@pytest.mark.asyncio
async def test_search(session):
    p = await projects.create_project(session, ProjectCreate(name="M4", prefix="MC4"))
    await mcp.create_test_suite(project_id=p.id, path="S")
    await mcp.create_test_case(project_id=p.id, suite_path="S", name="payment test")
    results = await mcp.search_test_cases(project_id=p.id, query="payment")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_record_test_run(session):
    p = await projects.create_project(session, ProjectCreate(name="M5", prefix="MC5"))
    await mcp.create_test_suite(project_id=p.id, path="S")
    case = await mcp.create_test_case(project_id=p.id, suite_path="S", name="c")
    from app.models.plan import TestPlan

    plan = TestPlan(project_id=p.id, name="P")
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    run = await mcp.record_test_run(
        case_id=case["id"], plan_id=plan.id, build_name="b1", status="pass",
    )
    assert run["status"] == "pass"
    assert run["build_id"] is not None
```

- [ ] **Step 2: Run it — verify failure**

Run: `pytest tests/test_mcp.py -v`
Expected: FAIL — `app.mcp_server.server` not built.

- [ ] **Step 3: Write `app/mcp_server/server.py`**

```python
"""AgentQA MCP server.

Tools wrap the service layer directly. Each tool opens its own DB session.
Phase 1 implements the 6 entity-backed tools; the rest are registered as
explicit stubs raising NotImplementedError until their phase lands.
"""
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from app.db import SessionLocal
from app.schemas.execution import ExecutionCreate, StepResultIn
from app.schemas.testcase import StepIn, TestCaseCreate
from app.services import executions, suites, testcases

mcp = FastMCP("agentqa")


@asynccontextmanager
async def _session():
    async with SessionLocal() as s:
        yield s


def _version_dump(out) -> dict | None:
    if out.current_version is None:
        return None
    cv = out.current_version
    return {
        "version": cv.version,
        "summary": cv.summary,
        "preconditions": cv.preconditions,
        "importance": cv.importance,
        "execution_type": cv.execution_type,
        "status": cv.status,
        "steps": [
            {"step_number": s.step_number, "action": s.action,
             "expected_result": s.expected_result}
            for s in cv.steps
        ],
    }


def _case_dump(out) -> dict:
    return {
        "id": out.id,
        "external_id": out.external_id,
        "name": out.name,
        "suite_id": out.suite_id,
        "project_id": out.project_id,
        "current_version": _version_dump(out),
    }


# ---------- Phase 1: entity-backed tools ----------

@mcp.tool()
async def create_test_suite(project_id: int, path: str, details: str | None = None) -> dict:
    """Find-or-create a test suite by slash-delimited path, e.g. 'Auth/Login/OAuth'."""
    async with _session() as s:
        suite = await suites.find_or_create_path(s, project_id, path)
        return {"id": suite.id, "name": suite.name, "parent_id": suite.parent_id}


@mcp.tool()
async def create_test_case(
    project_id: int,
    suite_path: str,
    name: str,
    summary: str | None = None,
    preconditions: str | None = None,
    steps: list[dict] | None = None,
    importance: int = 2,
    execution_type: str = "manual",
) -> dict:
    """Create a full test case (with version 1 + steps) under a suite path."""
    async with _session() as s:
        suite = await suites.find_or_create_path(s, project_id, suite_path)
        tc = await testcases.create_test_case(
            s, suite.id,
            TestCaseCreate(
                name=name, summary=summary, preconditions=preconditions,
                importance=importance, execution_type=execution_type,
                steps=[StepIn(**st) for st in (steps or [])],
            ),
        )
        out = await testcases.get_test_case(s, tc.id)
        return _case_dump(out)


@mcp.tool()
async def bulk_create_test_cases(
    project_id: int, suite_path: str, cases: list[dict]
) -> list[dict]:
    """Create many test cases under one suite path in a single call."""
    async with _session() as s:
        suite = await suites.find_or_create_path(s, project_id, suite_path)
        created = []
        for c in cases:
            tc = await testcases.create_test_case(
                s, suite.id,
                TestCaseCreate(
                    name=c["name"], summary=c.get("summary"),
                    preconditions=c.get("preconditions"),
                    importance=c.get("importance", 2),
                    execution_type=c.get("execution_type", "manual"),
                    steps=[StepIn(**st) for st in c.get("steps", [])],
                ),
            )
            out = await testcases.get_test_case(s, tc.id)
            created.append(_case_dump(out))
        return created


@mcp.tool()
async def get_test_case(
    case_id: int | None = None,
    external_id: str | None = None,
    project_id: int | None = None,
) -> dict:
    """Fetch a test case (current version + steps) by id, or external_id + project_id."""
    async with _session() as s:
        if case_id is not None:
            out = await testcases.get_test_case(s, case_id)
        elif external_id is not None and project_id is not None:
            out = await testcases.get_by_external_id(s, project_id, external_id)
        else:
            raise ValueError("provide case_id, or external_id + project_id")
        return _case_dump(out)


@mcp.tool()
async def search_test_cases(project_id: int, query: str) -> list[dict]:
    """Search test cases by name substring — call before creating duplicates."""
    async with _session() as s:
        rows = await testcases.search_test_cases(s, project_id, query)
        return [{"id": r.id, "external_id": r.external_id, "name": r.name} for r in rows]


@mcp.tool()
async def record_test_run(
    case_id: int,
    plan_id: int,
    build_name: str,
    status: str,
    commit_id: str | None = None,
    step_results: list[dict] | None = None,
    notes: str | None = None,
    session_id: str | None = None,
) -> dict:
    """Record an execution result. Build is upserted by (plan, build_name)."""
    async with _session() as s:
        ex = await executions.record_execution(
            s,
            ExecutionCreate(
                case_id=case_id, plan_id=plan_id, build_name=build_name,
                commit_id=commit_id, status=status,
                step_results=[StepResultIn(**sr) for sr in (step_results or [])],
                notes=notes, session_id=session_id,
            ),
            tester_id=None,  # MCP callers are agents
        )
        return {"id": ex.id, "status": ex.status, "build_id": ex.build_id,
                "version_id": ex.version_id}


# ---------- Deferred tools (registered, bodies land in later phases) ----------

_DEFERRED = [
    "get_failure_context", "search_similar_failures", "get_agent_execution_history",
    "get_execution_evidence", "list_unverified_claims", "verify_claim",
    "evaluate_test_case", "create_audit_report", "get_coverage_gaps",
    "list_assignments", "assign_test", "create_requirement", "upload_artifact",
]


def _make_stub(tool_name: str):
    @mcp.tool(name=tool_name)
    async def _stub(**kwargs) -> dict:
        raise NotImplementedError(f"{tool_name} is implemented in a later phase")
    return _stub


for _name in _DEFERRED:
    _make_stub(_name)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
```

Create empty `app/mcp_server/__init__.py`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_mcp.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Smoke-test the server starts (stdio)**

```bash
timeout 2 python -m app.mcp_server.server || true
```

Expected: starts and waits on stdio (timeout kills it; no traceback).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: MCP server with 6 phase-1 workflow tools + deferred stubs"
```

---

## Task 10: CLI Scaffold (`agentqa`)

A Typer app that wraps the REST API via httpx. Reads `AGENTQA_API_URL` and `AGENTQA_API_KEY` from the environment. Phase 1 covers project / suite / case / run verbs, including the `--from-file` ergonomics.

**Files:**
- Create: `cli/__init__.py`, `cli/main.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test `tests/test_cli.py`**

The CLI's HTTP calls go through a small `_request` helper; we test that helper's URL/header construction and the command wiring with a mocked client.

```python
import json

import pytest
from typer.testing import CliRunner

from cli import main as cli

runner = CliRunner()


def test_request_builds_url_and_headers(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {"ok": True}

        def raise_for_status(self):
            pass

    def fake_request(method, url, headers=None, json=None, params=None):
        captured.update(method=method, url=url, headers=headers, json=json, params=params)
        return FakeResp()

    monkeypatch.setattr(cli.httpx, "request", fake_request)
    monkeypatch.setenv("AGENTQA_API_URL", "http://x:8000")
    monkeypatch.setenv("AGENTQA_API_KEY", "aqa_test")
    out = cli._request("GET", "/api/v1/projects")
    assert out == {"ok": True}
    assert captured["url"] == "http://x:8000/api/v1/projects"
    assert captured["headers"]["X-API-Key"] == "aqa_test"


def test_project_create_invokes_post(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_request", lambda m, p, **k: calls.append((m, p, k)) or {"id": 1})
    result = runner.invoke(cli.app, ["project", "create", "Demo", "--prefix", "DEMO"])
    assert result.exit_code == 0
    assert calls[0][0] == "POST"
    assert calls[0][1] == "/api/v1/projects"


def test_case_create_from_file(monkeypatch, tmp_path):
    spec = tmp_path / "case.json"
    spec.write_text(json.dumps({"name": "c", "steps": [{"action": "go"}]}))
    calls = []
    monkeypatch.setattr(cli, "_request", lambda m, p, **k: calls.append((m, p, k)) or {"id": 9})
    result = runner.invoke(
        cli.app, ["case", "create", "5", "--from-file", str(spec)]
    )
    assert result.exit_code == 0
    assert calls[0][2]["json"]["name"] == "c"
```

- [ ] **Step 2: Run it — verify failure**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL — `cli.main` not built.

- [ ] **Step 3: Write `cli/main.py`**

```python
import json
import os
from pathlib import Path

import httpx
import typer

app = typer.Typer(help="AgentQA CLI")
project_app = typer.Typer(help="Manage projects")
suite_app = typer.Typer(help="Manage suites")
case_app = typer.Typer(help="Manage test cases")
run_app = typer.Typer(help="Record/inspect executions")
app.add_typer(project_app, name="project")
app.add_typer(suite_app, name="suite")
app.add_typer(case_app, name="case")
app.add_typer(run_app, name="run")


def _request(method: str, path: str, *, json_body=None, params=None) -> dict:
    base = os.environ.get("AGENTQA_API_URL", "http://localhost:8000")
    headers = {}
    api_key = os.environ.get("AGENTQA_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    resp = httpx.request(method, base + path, headers=headers, json=json_body, params=params)
    resp.raise_for_status()
    return resp.json()


def _print(data) -> None:
    typer.echo(json.dumps(data, indent=2, default=str))


@project_app.command("list")
def project_list():
    _print(_request("GET", "/api/v1/projects"))


@project_app.command("create")
def project_create(name: str, prefix: str = typer.Option(..., "--prefix")):
    _print(_request("POST", "/api/v1/projects", json_body={"name": name, "prefix": prefix}))


@project_app.command("get")
def project_get(project_id: int):
    _print(_request("GET", f"/api/v1/projects/{project_id}"))


@suite_app.command("create")
def suite_create(
    project_id: int,
    name: str = typer.Option(..., "--name"),
    parent: int | None = typer.Option(None, "--parent"),
):
    _print(
        _request(
            "POST", f"/api/v1/projects/{project_id}/suites",
            json_body={"name": name, "parent_id": parent},
        )
    )


@suite_app.command("tree")
def suite_tree(suite_id: int):
    _print(_request("GET", f"/api/v1/suites/{suite_id}/tree"))


@case_app.command("create")
def case_create(
    suite_id: int,
    name: str = typer.Option(None, "--name"),
    from_file: Path = typer.Option(None, "--from-file"),
):
    if from_file:
        body = json.loads(from_file.read_text())
    elif name:
        body = {"name": name}
    else:
        raise typer.BadParameter("provide --name or --from-file")
    _print(_request("POST", f"/api/v1/suites/{suite_id}/cases", json_body=body))


@case_app.command("get")
def case_get(case_id: int):
    _print(_request("GET", f"/api/v1/cases/{case_id}"))


@run_app.command("record")
def run_record(
    case_id: int,
    plan: int = typer.Option(..., "--plan"),
    build: str = typer.Option(..., "--build"),
    status: str = typer.Option(..., "--status"),
    from_file: Path = typer.Option(None, "--steps-file"),
    notes: str = typer.Option(None, "--notes"),
):
    body = {"case_id": case_id, "plan_id": plan, "build_name": build, "status": status}
    if from_file:
        body["step_results"] = json.loads(from_file.read_text())
    if notes:
        body["notes"] = notes
    _print(_request("POST", "/api/v1/executions", json_body=body))


@run_app.command("list")
def run_list(case: int = typer.Option(..., "--case")):
    _print(_request("GET", f"/api/v1/cases/{case}/executions"))


if __name__ == "__main__":
    app()
```

Create empty `cli/__init__.py`.

> **Note on the test:** `test_request_builds_url_and_headers` patches `cli.httpx.request` and calls `_request("GET", path)` with no body — the signature uses keyword-only `json_body`/`params`, so adjust the test's `fake_request` to accept `json=None` mapping. The plan's `_request` passes `json=json_body` to `httpx.request`; the fake signature in the test already matches httpx's `request(method, url, headers, json, params)`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: End-to-end manual smoke (optional, needs API running)**

```bash
docker compose up -d postgres
alembic upgrade head
uvicorn app.main:app &
# create an admin user via python one-liner or a seed script, issue a key, then:
export AGENTQA_API_URL=http://localhost:8000
export AGENTQA_API_KEY=<key>
agentqa project create "Demo" --prefix DEMO
```

Expected: prints the created project JSON.

- [ ] **Step 6: Run the FULL suite**

Run: `pytest -v`
Expected: ALL PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: agentqa CLI scaffold (project/suite/case/run verbs)"
```

---

## Task 11: Seed Script & README

A small seed creates the default roles and an admin user so the system is usable immediately. README documents bring-up.

**Files:**
- Create: `scripts/seed.py`, `README.md`
- Test: `tests/test_seed.py`

- [ ] **Step 1: Write the failing test `tests/test_seed.py`**

```python
import pytest

from scripts.seed import seed_defaults
from app.models.user import Role, User
from sqlalchemy import select


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
```

- [ ] **Step 2: Run it — verify failure**

Run: `pytest tests/test_seed.py -v`
Expected: FAIL.

- [ ] **Step 3: Write `scripts/seed.py`**

```python
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import SessionLocal
from app.models.user import Role, User
from app.services import auth

DEFAULT_ROLES = ["Admin", "Project Lead", "Test Designer", "Tester", "Guest"]


async def seed_defaults(session: AsyncSession, admin_login: str, admin_password: str) -> None:
    existing_roles = {
        r.name for r in (await session.execute(select(Role))).scalars().all()
    }
    role_by_name: dict[str, Role] = {}
    for name in DEFAULT_ROLES:
        if name not in existing_roles:
            role = Role(name=name)
            session.add(role)
            await session.flush()
            role_by_name[name] = role
    await session.flush()
    admin_role = (
        await session.execute(select(Role).where(Role.name == "Admin"))
    ).scalar_one()

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
```

Create empty `scripts/__init__.py`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_seed.py -v`
Expected: PASS.

- [ ] **Step 5: Write `README.md`**

````markdown
# AgentQA

Test management for agentic coding — TestLink-equivalent, with a REST API, an MCP server, and a CLI over one shared service layer.

## Quick start

```bash
cp .env.example .env
docker compose up -d postgres minio
pip install -e ".[dev]"
alembic upgrade head
python -m scripts.seed          # creates admin/admin + default roles
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

## Get an API key (for agents/CLI)

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login \
  -H 'content-type: application/json' \
  -d '{"login":"admin","password":"admin"}' | jq -r .access_token)
KEY=$(curl -s -X POST localhost:8000/api/v1/auth/token \
  -H "authorization: Bearer $TOKEN" | jq -r .api_key)
export AGENTQA_API_KEY=$KEY AGENTQA_API_URL=http://localhost:8000
```

## CLI

```bash
agentqa project create "Demo" --prefix DEMO
agentqa suite create 1 --name "Auth"
agentqa case create 1 --from-file case.json
agentqa run record 1 --plan 1 --build b1 --status pass
```

## MCP server

```bash
python -m app.mcp_server.server   # stdio transport
```

## Tests

```bash
pytest -v
```
````

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: seed script (roles + admin) and README"
```

---

## Final Verification

- [ ] **Run the full suite**

Run: `pytest -v`
Expected: every test passes across auth, projects, suites, testcases, executions, mcp, cli, seed.

- [ ] **Lint**

Run: `ruff check . && ruff format --check .`
Expected: clean (fix with `ruff format .` and `ruff check --fix .` if needed).

- [ ] **Bring the stack up clean from scratch**

```bash
docker compose down -v
docker compose up -d postgres
alembic upgrade head
python -m scripts.seed
uvicorn app.main:app &
curl -s localhost:8000/health
```

Expected: `{"status":"ok"}` and a fully migrated DB.

---

## Phase 1 Done — What Exists

- Full schema (all ~35 tables) migrated, pgvector extension enabled
- Auth: password login → JWT, API-key issue + use, dual-credential dependency
- CRUD + services: projects, suites (path resolution + tree), versioned test cases, execution recording with build upsert
- MCP server: 6 working workflow tools + 13 deferred stubs
- CLI: project / suite / case / run verbs with `--from-file`
- Seed + README + docker-compose

## Deferred to Later Phases

- **Phase 2:** test plan/build/milestone services + endpoints, evidence (artifacts→MinIO, claims, verifications, reasoning), embeddings + `search_similar_failures`/`get_failure_context`, requirements + traceability, the 13 stub MCP tools, Evidence Viewer UI
- **Phase 3:** all 12 Next.js UI views
- **Phase 4:** Jira/GitHub/Mantis integrations, custom fields, LDAP/OAuth, import/export, plugins, inventory
