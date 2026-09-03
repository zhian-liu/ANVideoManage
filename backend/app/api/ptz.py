from pydantic import BaseModel, Field

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.registry import get_adapter
from app.core.deps import get_current_user
from app.database import get_db
from app.models import Device

router = APIRouter(
    prefix="/api/devices",
    tags=["ptz"],
    dependencies=[Depends(get_current_user)],
)


class MoveRequest(BaseModel):
    direction: str = Field(..., pattern="^(left|right|up|down)$")
    speed: float = Field(0.5, ge=0.1, le=1.0)


class ZoomRequest(BaseModel):
    direction: str = Field(..., pattern="^(in|out)$")
    speed: float = Field(0.5, ge=0.1, le=1.0)


async def _get_device(device_id: int, db: AsyncSession) -> Device:
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    if not device.ptz_enabled:
        raise HTTPException(status_code=400, detail="该设备未启用云台控制")
    return device


@router.post("/{device_id}/ptz/move")
async def ptz_move(
    device_id: int, body: MoveRequest, db: AsyncSession = Depends(get_db)
):
    device = await _get_device(device_id, db)
    adapter = get_adapter(device.access_type)
    try:
        await adapter.ptz_move(device, body.direction, body.speed)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="该设备不支持云台控制")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"云台控制失败: {exc}")
    return {"ok": True}


@router.post("/{device_id}/ptz/zoom")
async def ptz_zoom(
    device_id: int, body: ZoomRequest, db: AsyncSession = Depends(get_db)
):
    device = await _get_device(device_id, db)
    adapter = get_adapter(device.access_type)
    try:
        await adapter.ptz_zoom(device, body.direction, body.speed)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="该设备不支持云台变焦")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"云台变焦失败: {exc}")
    return {"ok": True}


@router.post("/{device_id}/ptz/stop")
async def ptz_stop(device_id: int, db: AsyncSession = Depends(get_db)):
    device = await _get_device(device_id, db)
    adapter = get_adapter(device.access_type)
    try:
        await adapter.ptz_stop(device)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="该设备不支持云台控制")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"云台停止失败: {exc}")
    return {"ok": True}
