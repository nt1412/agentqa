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
