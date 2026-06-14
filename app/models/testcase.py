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
