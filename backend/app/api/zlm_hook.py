"""ZLMediaKit WebHook 回调端点（供 ZLMediaKit 推送事件，无需登录）。"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Device, Recording

router = APIRouter(prefix="/api/zlm/hook", tags=["zlm-hook"])


def _device_id_from_stream(stream) -> int | None:
    if not stream or not stream.startswith("device_"):
        return None
    try:
        return int(stream[len("device_") :])
    except ValueError:
        return None


@router.post("/on_stream_changed")
async def on_stream_changed(body: dict, db: AsyncSession = Depends(get_db)):
    device_id = _device_id_from_stream(body.get("stream"))
    if device_id is not None:
        device = await db.get(Device, device_id)
        if device is not None:
            device.status = "online" if bool(body.get("regist")) else "offline"
            await db.commit()
    return {"code": 0}


@router.post("/on_record_mp4")
async def on_record_mp4(body: dict, db: AsyncSession = Depends(get_db)):
    device_id = _device_id_from_stream(body.get("stream"))
    if device_id is None:
        return {"code": 0}
    device = await db.get(Device, device_id)
    if device is None:
        return {"code": 0}

    start_ts = body.get("start_time")
    if start_ts:
        start_dt = datetime.fromtimestamp(float(start_ts), tz=timezone.utc).replace(
            tzinfo=None
        )
    else:
        start_dt = datetime.utcnow()
    time_len = float(body.get("time_len") or 0)
    end_dt = start_dt + timedelta(seconds=time_len)

    recording = Recording(
        device_id=device_id,
        start_time=start_dt,
        end_time=end_dt,
        file_path=body.get("file_path") or "",
        file_name=body.get("file_name") or "",
        file_size=int(body.get("file_size") or 0),
    )
    db.add(recording)
    await db.commit()
    return {"code": 0}
