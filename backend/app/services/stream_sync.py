"""设备流代理同步：根据设备配置向 ZLMediaKit 下发/更新拉流。"""
from app.adapters.registry import get_adapter
from app.models import Device
from app.services.zlmediakit import zlm


async def apply_stream(device: Device) -> None:
    """按设备当前配置向 ZLMediaKit 下发/更新拉流代理（失败不影响入库）。"""
    if not device.enabled:
        await zlm.del_stream_proxy(device.id)
        return
    try:
        adapter = get_adapter(device.access_type)
        rtsp = await adapter.resolve_stream(device)
    except Exception:
        return
    if not rtsp:
        return
    try:
        await zlm.add_stream_proxy(device.id, rtsp, enable_mp4=device.record_enabled)
    except Exception:
        pass
