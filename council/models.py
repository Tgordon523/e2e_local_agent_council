import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, Uuid, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# Dialect-portable column types. On Postgres these resolve to the native `uuid`
# and `jsonb` types declared in alembic/init.sql (no schema change); on other
# dialects (SQLite, used by the test suite) they fall back to CHAR(32) and TEXT,
# so the real models can be created in-memory without a parallel test schema.
_UUID = Uuid().with_variant(PG_UUID(as_uuid=True), "postgresql")
_JSON = JSON().with_variant(JSONB, "postgresql")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=uuid.uuid4)
    idea_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    final_verdict: Mapped[Optional[str]] = mapped_column(Text)

    results: Mapped[list["AgentResult"]] = relationship(
        "AgentResult",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AgentResult(Base):
    __tablename__ = "agent_results"

    id: Mapped[uuid.UUID] = mapped_column(_UUID, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(_UUID, ForeignKey("runs.id"), nullable=False)
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    report_text: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(_JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    run: Mapped["Run"] = relationship("Run", back_populates="results")
