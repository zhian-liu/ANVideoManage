"""RTSP/ONVIF 标准协议适配器。

- resolve_stream：优先使用显式 RTSP 地址，否则尝试 ONVIF GetStreamUri 自动获取，
  最后回退到通用 RTSP 路径。
- PTZ / 抓图：通过 ONVIF 实现（同步库，放入线程池执行避免阻塞事件循环）。
"""
import asyncio

from app.adapters.base import CameraAdapter
from app.models import Device

_DIRECTIONS = {
    "left": (-1.0, 0.0),
    "right": (1.0, 0.0),
    "up": (0.0, 1.0),
    "down": (0.0, -1.0),
}


class OnvifAdapter(CameraAdapter):
    access_type = "onvif"

    async def resolve_stream(self, device: Device) -> str:
        if device.rtsp_url:
            return device.rtsp_url
        # 尝试通过 ONVIF 获取真实 RTSP 地址
        uri = await asyncio.to_thread(self._onvif_stream_uri, device)
        if uri:
            return uri
        # 回退：通用 RTSP 路径（可能因厂商而异，建议填写 rtsp_url）
        return f"rtsp://{device.username}:{device.password}@{device.ip}:{device.port}/"

    async def ptz_move(self, device: Device, direction: str, speed: float = 0.5) -> None:
        if direction not in _DIRECTIONS:
            raise ValueError(f"未知方向: {direction}")
        x, y = _DIRECTIONS[direction]
        await asyncio.to_thread(
            self._onvif_continuous_move, device, x * speed, y * speed, 0.0
        )

    async def ptz_stop(self, device: Device) -> None:
        await asyncio.to_thread(self._onvif_stop, device)

    async def ptz_zoom(self, device: Device, direction: str, speed: float = 0.5) -> None:
        z = 1.0 if direction == "in" else -1.0
        await asyncio.to_thread(
            self._onvif_continuous_move, device, 0.0, 0.0, z * speed
        )

    async def snapshot(self, device: Device) -> bytes:
        return await asyncio.to_thread(self._onvif_snapshot, device)

    # ---- 同步实现（在线程池中执行）----

    @staticmethod
    def _camera(device: Device):
        from onvif import ONVIFCamera

        return ONVIFCamera(device.ip, device.onvif_port, device.username, device.password)

    @classmethod
    def _profile_token(cls, device: Device):
        media = cls._camera(device).create_media_service()
        return media.GetProfiles()[0].token

    @classmethod
    def _onvif_stream_uri(cls, device: Device) -> str | None:
        try:
            media = cls._camera(device).create_media_service()
            token = media.GetProfiles()[0].token
            request = media.create_type("GetStreamUri")
            request.StreamSetup = {
                "Stream": "RTP-Unicast",
                "Transport": {"Protocol": "RTSP"},
            }
            request.ProfileToken = token
            result = media.GetStreamUri(request)
            return getattr(result, "Uri", None)
        except Exception:
            return None

    @classmethod
    def _onvif_continuous_move(
        cls, device: Device, pan: float, tilt: float, zoom: float
    ) -> None:
        cam = cls._camera(device)
        ptz = cam.create_ptz_service()
        token = cls._profile_token(device)
        request = ptz.create_type("ContinuousMove")
        request.ProfileToken = token
        request.Velocity = {
            "PanTilt": {"x": pan, "y": tilt},
            "Zoom": {"x": zoom},
        }
        ptz.ContinuousMove(request)

    @classmethod
    def _onvif_stop(cls, device: Device) -> None:
        cam = cls._camera(device)
        ptz = cam.create_ptz_service()
        token = cls._profile_token(device)
        ptz.Stop({"ProfileToken": token, "PanTilt": True, "Zoom": True})

    @classmethod
    def _onvif_snapshot(cls, device: Device) -> bytes:
        import httpx

        media = cls._camera(device).create_media_service()
        token = media.GetProfiles()[0].token
        request = media.create_type("GetSnapshotUri")
        request.ProfileToken = token
        result = media.GetSnapshotUri(request)
        url = getattr(result, "Uri", None)
        if not url:
            raise RuntimeError("ONVIF 未返回抓图地址")
        resp = httpx.get(url, auth=(device.username, device.password), timeout=10)
        resp.raise_for_status()
        return resp.content
