"""摄像机适配器统一抽象。各接入方式（ONVIF / 云 API / 私有 SDK）实现该接口。"""
from abc import ABC, abstractmethod

from app.models import Device


class CameraAdapter(ABC):
    """所有摄像机接入方式的基类。

    子类需设置 access_type，并实现 resolve_stream；PTZ / 抓图按能力覆盖。
    """

    access_type: str = ""

    @abstractmethod
    async def resolve_stream(self, device: Device) -> str:
        """返回可交给 ZLMediaKit 拉流的地址（通常为 RTSP URL）。"""

    async def ptz_move(self, device: Device, direction: str, speed: float = 0.5) -> None:
        raise NotImplementedError(f"{self.access_type} 适配器不支持云台控制")

    async def ptz_stop(self, device: Device) -> None:
        raise NotImplementedError(f"{self.access_type} 适配器不支持云台控制")

    async def ptz_zoom(self, device: Device, direction: str, speed: float = 0.5) -> None:
        raise NotImplementedError(f"{self.access_type} 适配器不支持云台变焦")

    async def snapshot(self, device: Device) -> bytes:
        raise NotImplementedError(f"{self.access_type} 适配器不支持抓图")
