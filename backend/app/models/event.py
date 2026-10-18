"""ORM model for one stored event. Columns mirror docs/event-schema.md."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.database import Base, UTCDateTime


class EventRecord(Base):
    __tablename__ = "events"
    # Second line of defence: the database itself refuses two events
    # with the same sequence number in one run.
    __table_args__ = (UniqueConstraint("run_id", "sequence", name="uq_event_run_sequence"),)

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), index=True)
    parent_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sequence: Mapped[int] = mapped_column(Integer)
    schema_version: Mapped[str] = mapped_column(String(10))
    event_type: Mapped[str] = mapped_column(String(20), index=True)
    operation_name: Mapped[str] = mapped_column(String(100))
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(10))
    attributes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime)

    run = relationship("RunRecord", back_populates="events")
