from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.registry import get_adapter
from app.core.deps import get_current_user
from app.database import get_db
from app.models import Device
from app.services.stream_sync import apply_stream
from app.services.zlmediakit import flv_url, hls_url, stream_key, zlm

router = APIRouter(
    prefix="/api/streams",
    tags=["streams"],
    dependencies=[Depends(get_current_user)],
)


async def _get_device(device_id: int, db: AsyncSession) -> Device:
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device


@router.get("/{device_id}")
async def stream_info(device_id: int, db: AsyncSession = Depends(get_db)):
    device = await _get_device(device_id, db)
    online_streams = await zlm.online_streams()
    online = stream_key(device.id) in online_streams
    # 若流已因无观看被 ZLM 自动停止，则重新下发拉流
    if not online and device.enabled:
        await apply_stream(device)
        online = stream_key(device.id) in await zlm.online_streams()
    return {
        "device_id": device.id,
        "online": online,
        "flv_url": flv_url(device.id),
        "hls_url": hls_url(device.id),
    }


@router.post("/{device_id}/start")
async def start_stream(device_id: int, db: AsyncSession = Depends(get_db)):
    device = await _get_device(device_id, db)
    adapter = get_adapter(device.access_type)
    rtsp = await adapter.resolve_stream(device)
    if not rtsp:
        raise HTTPException(status_code=400, detail="无法解析拉流地址")
    await zlm.add_stream_proxy(device.id, rtsp, enable_mp4=device.record_enabled)
    return {"ok": True}


@router.post("/{device_id}/stop")
async def stop_stream(device_id: int, db: AsyncSession = Depends(get_db)):
    await _get_device(device_id, db)
    await zlm.del_stream_proxy(device_id)
    return {"ok": True}


@router.get("/{device_id}/snapshot")
async def snapshot(device_id: int, db: AsyncSession = Depends(get_db)):
    device = await _get_device(device_id, db)
    adapter = get_adapter(device.access_type)
    try:
        data = await adapter.snapshot(device)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="该设备不支持抓图")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"抓图失败: {exc}")
    return Response(content=data, media_type="image/jpeg")
