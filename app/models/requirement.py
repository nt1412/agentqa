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
