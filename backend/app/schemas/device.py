from datetime import datetime

from pydantic import BaseModel, Field


class DeviceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    vendor: str = "generic"
    access_type: str = "onvif"
    ip: str = ""
    port: int = 554
    username: str = ""
    password: str = ""
    rtsp_url: str = ""
    onvif_port: int = 80
    ptz_enabled: bool = False
    record_enabled: bool = True
    enabled: bool = True


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    name: str | None = None
    vendor: str | None = None
    access_type: str | None = None
    ip: str | None = None
    port: int | None = None
    username: str | None = None
    password: str | None = None
    rtsp_url: str | None = None
    onvif_port: int | None = None
    ptz_enabled: bool | None = None
    record_enabled: bool | None = None
    enabled: bool | None = None


class DeviceOut(DeviceBase):
    id: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
