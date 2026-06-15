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


class Annotation(Base, TimestampMixin):
    """A free-text note a human or agent attaches to any entity (a regression, a
    case, a build) — the collaboration trail. Polymorphic like the other junctions."""

    __tablename__ = "annotations"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)


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
