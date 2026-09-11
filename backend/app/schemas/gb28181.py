from datetime import datetime
from ipaddress import IPv4Address
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class GbConfig(BaseModel):
    enabled: bool = False
    sip_id: str = Field("34020000002000000001", pattern=r"^[0-9]{20}$")
    realm: str = Field("3402000000", pattern=r"^[0-9]{10}$")
    listen_ip: str = "0.0.0.0"
    advertise_ip: str = ""
    sip_port: int = Field(5060, ge=1, le=65535)
    media_ip: str = ""
    media_transport: Literal["udp", "tcp-passive"] = "udp"
    heartbeat_timeout: int = Field(180, ge=10, le=3600)
    invite_timeout: int = Field(15, ge=3, le=60)
    media_timeout: int = Field(15, ge=3, le=60)
    catalog_timeout: int = Field(30, ge=5, le=120)

    @field_validator("listen_ip", "advertise_ip", "media_ip")
    @classmethod
    def validate_ip(cls, value: str) -> str:
        value = value.strip()
        if value:
            address = IPv4Address(value)
            if address.is_multicast or str(address) == "255.255.255.255":
                raise ValueError("请填写单播 IPv4 地址")
            return str(address)
        return value

    @model_validator(mode="after")
    def require_addresses(self):
        if not self.listen_ip:
            raise ValueError("SIP 监听地址不能为空")
        if self.enabled and any(ip in {"", "0.0.0.0"} for ip in (self.advertise_ip, self.media_ip)):
            raise ValueError("启用国标前，请填写设备可达的 SIP 公告地址和媒体接收地址")
        return self


class GbDeviceCreate(BaseModel):
    id: str = Field(pattern=r"^[0-9]{20}$")
    name: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)
    enabled: bool = True

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value):
            raise ValueError("密码不能包含控制字符")
        return value


class GbDeviceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    password: str | None = Field(None, min_length=1, max_length=128)
    enabled: bool | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str | None) -> str | None:
        return GbDeviceCreate.validate_password(value) if value is not None else None


class GbDeviceOut(BaseModel):
    id: str
    name: str
    enabled: bool
    online: bool
    registered_until: datetime | None
    last_heartbeat: datetime | None
    remote_ip: str
    remote_port: int
    transport: str
    manufacturer: str
    model: str
    catalog_state: str
    catalog_expected: int | None
    catalog_received: int
    last_error: str


class GbLeaseRequest(BaseModel):
    lease_id: str | None = Field(None, pattern=r"^[a-f0-9]{32}$")
