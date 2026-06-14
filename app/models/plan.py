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
