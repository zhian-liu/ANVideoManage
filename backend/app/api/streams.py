import asyncio

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
    recording = await zlm.is_recording(device.id) if online else False
    return {
        "device_id": device.id,
        "online": online,
        "recording": recording,
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
    if not await zlm.add_stream_proxy(device.id, rtsp, enable_mp4=device.record_enabled):
        raise HTTPException(status_code=502, detail="启动设备流失败")
    return {"ok": True}


@router.post("/{device_id}/stop")
async def stop_stream(device_id: int, db: AsyncSession = Depends(get_db)):
    await _get_device(device_id, db)
    await zlm.del_stream_proxy(device_id)
    return {"ok": True}


@router.post("/{device_id}/record/start")
async def start_record(device_id: int, db: AsyncSession = Depends(get_db)):
    device = await _get_device(device_id, db)
    online = stream_key(device.id) in await zlm.online_streams()
    if not online:
        adapter = get_adapter(device.access_type)
        try:
            rtsp = await adapter.resolve_stream(device)
        except NotImplementedError:
            raise HTTPException(status_code=501, detail="该设备暂不支持录像")
        except Exception:
            raise HTTPException(status_code=502, detail="解析设备流失败")
        if not rtsp:
            raise HTTPException(status_code=400, detail="无法解析拉流地址")
        try:
            stream_started = await zlm.add_stream_proxy(
                device.id, rtsp, enable_mp4=device.record_enabled
            )
        except Exception:
            raise HTTPException(status_code=502, detail="启动设备流失败")
        if not stream_started:
            raise HTTPException(status_code=502, detail="启动设备流失败")

        # addStreamProxy 返回成功后，媒体源还需要一点时间完成注册。
        for _ in range(20):
            if stream_key(device.id) in await zlm.online_streams():
                break
            await asyncio.sleep(0.25)
        else:
            raise HTTPException(status_code=502, detail="设备流启动超时，无法开始录像")

    try:
        recording_started = await zlm.start_record(device.id)
    except Exception:
        raise HTTPException(status_code=502, detail="启动录像失败")
    if not recording_started:
        raise HTTPException(status_code=502, detail="启动录像失败")
    return {"ok": True, "recording": True}


@router.post("/{device_id}/record/stop")
async def stop_record(device_id: int, db: AsyncSession = Depends(get_db)):
    await _get_device(device_id, db)
    try:
        recording_stopped = await zlm.stop_record(device_id)
    except Exception:
        raise HTTPException(status_code=502, detail="停止录像失败")
    if not recording_stopped:
        raise HTTPException(status_code=502, detail="停止录像失败")
    return {"ok": True, "recording": False}


@router.get("/{device_id}/record/status")
async def record_status(device_id: int, db: AsyncSession = Depends(get_db)):
    await _get_device(device_id, db)
    return {"device_id": device_id, "recording": await zlm.is_recording(device_id)}


@router.get("/{device_id}/snapshot")
async def snapshot(device_id: int, db: AsyncSession = Depends(get_db)):
    device = await _get_device(device_id, db)
    adapter = get_adapter(device.access_type)
    data: bytes | None = None
    try:
        data = await adapter.snapshot(device)
    except NotImplementedError:
        data = None
    except Exception:
        data = None

    # ONVIF 抓图失败时，使用 ZLMediaKit 通过 RTSP 拉流生成 JPEG，
    # 这样显式填写 RTSP 地址的设备也可以抓拍。
    if not data:
        try:
            rtsp = await adapter.resolve_stream(device)
            if not rtsp:
                raise RuntimeError("empty stream url")
            data = await zlm.get_snapshot(rtsp)
        except NotImplementedError:
            raise HTTPException(status_code=501, detail="该设备不支持抓图")
        except Exception:
            raise HTTPException(status_code=502, detail="抓图失败，请检查设备和 RTSP 配置")
    return Response(content=data, media_type="image/jpeg")
