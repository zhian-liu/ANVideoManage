from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Recording(Base):
    """录像索引表，由 ZLMediaKit on_record_mp4 WebHook 回调写入。"""

    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id"), index=True, nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    file_path: Mapped[str] = mapped_column(String(512), default="")
    file_name: Mapped[str] = mapped_column(String(256), default="")
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
