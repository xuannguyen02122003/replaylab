"""ORM model for a run.

The summary columns (status, completeness, counts...) are derived from the
run's events by services/summary.py and refreshed on every ingest. They are
stored so the run list can be filtered and sorted without loading events.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.database import Base, UTCDateTime


class RunRecord(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(10), index=True)  # ok | error | unknown
    completeness: Mapped[str] = mapped_column(String(12), index=True)  # complete | incomplete
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    event_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    received_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)

    events = relationship("EventRecord", back_populates="run", cascade="all, delete-orphan")
