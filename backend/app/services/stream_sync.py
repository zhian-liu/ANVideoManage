"""设备流代理同步：根据设备配置向 ZLMediaKit 下发/更新拉流。"""
import asyncio
import logging

from sqlalchemy import or_, select

from app.adapters.registry import get_adapter
from app.database import SessionLocal
from app.models import Device
from app.observability import capture_exception
from app.services.zlmediakit import stream_key, zlm

logger = logging.getLogger(__name__)
RECORDING_POLICY_INTERVAL_SECONDS = 60


async def apply_stream(device: Device, *, replace: bool = False) -> bool:
    """Apply options to a new proxy; existing proxies must be replaced."""
    try:
        if device.access_type == "gb28181":
            from app.services.gb_runtime import gb_runtime
            await gb_runtime.apply_device(device)
            return True
        if replace or not device.enabled:
            try:
                await zlm.stop_record(device.id)
            except Exception:
                # Removing the proxy also stops its recorder; still try it.
                logger.warning("Could not stop recorder for device %s before replacing proxy", device.id)
            if not await zlm.del_stream_proxy(device.id):
                return False
        if not device.enabled:
            return True
        adapter = get_adapter(device.access_type)
        rtsp = await adapter.resolve_stream(device)
        if not rtsp:
            return False
        return await zlm.add_stream_proxy(device.id, rtsp, enable_mp4=device.record_enabled)
    except Exception as exc:
        logger.exception("Could not synchronize stream for device %s", device.id)
        capture_exception(exc)
        return False


async def reconcile_disabled_recordings() -> None:
    """Repair stale proxies left running by older backends or interrupted updates."""
    async with SessionLocal() as db:
        devices = (
            await db.scalars(
                select(Device).where(or_(Device.enabled.is_(False), Device.record_enabled.is_(False)))
            )
        ).all()
    if not devices:
        return
    online = await zlm.online_streams()
    for device in devices:
        if stream_key(device.id) in online and await zlm.is_recording(device.id):
            # Network checks can take time; use the latest switch before acting.
            async with SessionLocal() as db:
                current = await db.get(Device, device.id)
            if current is not None and (not current.enabled or not current.record_enabled):
                await apply_stream(current, replace=True)


async def run_recording_policy() -> None:
    while True:
        try:
            await reconcile_disabled_recordings()
        except Exception as exc:
            logger.exception("Could not reconcile recording switches; will retry")
            capture_exception(exc)
        await asyncio.sleep(RECORDING_POLICY_INTERVAL_SECONDS)
