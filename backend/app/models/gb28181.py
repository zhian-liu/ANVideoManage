"""GB registration, catalog and recoverable media allocations (no legacy ALTERs)."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GbDevice(Base):
    __tablename__ = "gb_devices"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    password: Mapped[str] = mapped_column(String(128))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    registered_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    remote_ip: Mapped[str] = mapped_column(String(64), default="")
    remote_port: Mapped[int] = mapped_column(Integer, default=0)
    transport: Mapped[str] = mapped_column(String(8), default="")
    manufacturer: Mapped[str] = mapped_column(String(128), default="")
    model: Mapped[str] = mapped_column(String(128), default="")
    catalog_sn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    catalog_expected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    catalog_received: Mapped[int] = mapped_column(Integer, default=0)
    catalog_state: Mapped[str] = mapped_column(String(16), default="idle")
    catalog_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GbChannel(Base):
    __tablename__ = "gb_channels"
    __table_args__ = (UniqueConstraint("gb_device_id", "channel_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    gb_device_id: Mapped[str] = mapped_column(ForeignKey("gb_devices.id"), index=True)
    channel_id: Mapped[str] = mapped_column(String(20))
    # Non-video catalog entries count toward SumNum, but have no playable Device.
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id"), unique=True, nullable=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    manufacturer: Mapped[str] = mapped_column(String(128), default="")
    parent_id: Mapped[str] = mapped_column(String(20), default="")
    status: Mapped[str] = mapped_column(String(16), default="ON")
    present: Mapped[bool] = mapped_column(Boolean, default=True)
    catalog_sn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    record_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GbStreamSession(Base):
    __tablename__ = "gb_stream_sessions"

    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(32), unique=True)
    ssrc: Mapped[int] = mapped_column(Integer)
    rtp_port: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(16), default="allocating")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
