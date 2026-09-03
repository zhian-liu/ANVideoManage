from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Device(Base):
    """摄像机设备表。

    access_type 取值：
      - "onvif": RTSP/ONVIF 标准协议（MVP 完整支持）
      - "cloud": 厂商云 API（预留）
      - "sdk":   厂商私有 SDK（预留）
    """

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    vendor: Mapped[str] = mapped_column(String(64), default="generic")
    access_type: Mapped[str] = mapped_column(String(32), default="onvif")

    # 直连参数（onvif / sdk 使用）
    ip: Mapped[str] = mapped_column(String(64), default="")
    port: Mapped[int] = mapped_column(Integer, default=554)
    username: Mapped[str] = mapped_column(String(64), default="")
    password: Mapped[str] = mapped_column(String(128), default="")
    rtsp_url: Mapped[str] = mapped_column(String(512), default="")
    onvif_port: Mapped[int] = mapped_column(Integer, default=80)

    ptz_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    record_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # 在线状态：unknown / online / offline
    status: Mapped[str] = mapped_column(String(16), default="unknown")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
