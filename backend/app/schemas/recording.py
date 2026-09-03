from datetime import datetime

from pydantic import BaseModel


class RecordingOut(BaseModel):
    id: int
    device_id: int
    start_time: datetime
    end_time: datetime
    file_path: str
    file_name: str
    file_size: int
    created_at: datetime

    class Config:
        from_attributes = True
