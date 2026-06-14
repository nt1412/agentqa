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
