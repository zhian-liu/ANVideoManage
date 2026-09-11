from app.adapters.base import CameraAdapter
from app.models import Device


class Gb28181Adapter(CameraAdapter):
    """GB media must be established by the session service, never addStreamProxy."""
    access_type = "gb28181"

    async def resolve_stream(self, device: Device) -> str:
        raise NotImplementedError("国标设备使用 SIP/RTP 点播会话，不提供摄像机 RTSP 拉流地址")
