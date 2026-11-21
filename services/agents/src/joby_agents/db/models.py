"""Tables owned by the agent service, in the `agents` schema (ARCHITECTURE §6.2).

LangGraph checkpointer tables also live in this schema but are created by the
checkpointer itself (see joby_agents.graphs.checkpointer), not by Alembic.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "agents"


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA)


class QueueStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    awaiting_approval = "awaiting_approval"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


TERMINAL_STATUSES = frozenset({QueueStatus.completed, QueueStatus.failed, QueueStatus.cancelled})


class RunQueue(Base):
    __tablename__ = "run_queue"
    __table_args__ = (
        Index("ix_run_queue_claimable", "status", "created_at"),
        Index("ix_run_queue_tenant_status", "tenant_id", "status"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[QueueStatus] = mapped_column(
        Enum(QueueStatus, name="queue_status", schema=SCHEMA),
        default=QueueStatus.queued,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    claimed_by: Mapped[str | None] = mapped_column(String(128))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)
    error: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Outbox(Base):
    """Transactional outbox: written in the same transaction as the state change."""

    __tablename__ = "outbox"
    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_outbox_run_seq"),
        Index("ix_outbox_pending", "next_attempt_at", postgresql_where="delivered_at IS NULL"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("run_queue.run_id", ondelete="CASCADE")
    )
    seq: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Artifact(Base):
    """Intermediate outputs (raw scraped pages, prompts) kept until expires_at."""

    __tablename__ = "artifacts"
    __table_args__ = (Index("ix_artifacts_expires_at", "expires_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("run_queue.run_id", ondelete="CASCADE")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(String(64))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
