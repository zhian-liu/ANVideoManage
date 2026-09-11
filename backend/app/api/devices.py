from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models import Device, GbChannel, Recording
from app.schemas.device import DeviceCreate, DeviceOut, DeviceUpdate
from app.services.stream_sync import apply_stream
from app.services.zlmediakit import stream_key, zlm
from app.services.gb_catalog import channel_statuses

router = APIRouter(
    prefix="/api/devices",
    tags=["devices"],
    dependencies=[Depends(get_current_user)],
)


def _status(device: Device, online: set[str], gb_status: dict[int, str] | None = None) -> str:
    if not device.enabled:
        return "unknown"
    if device.access_type == "gb28181":
        return (gb_status or {}).get(device.id, "offline")
    return "online" if stream_key(device.id) in online else "offline"


@router.post("", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
async def create_device(body: DeviceCreate, db: AsyncSession = Depends(get_db)):
    if body.access_type == "gb28181":
        raise HTTPException(400, "国标通道由目录同步创建，请先在国标接入页面预置注册设备")
    device = Device(**body.model_dump())
    db.add(device)
    await db.commit()
    await db.refresh(device)
    await apply_stream(device)
    return device


@router.get("", response_model=list[DeviceOut])
async def list_devices(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Device).order_by(Device.id))
    devices = result.scalars().all()
    online = await zlm.online_streams()
    gb_status = await channel_statuses(db) if any(d.access_type == "gb28181" for d in devices) else {}
    for d in devices:
        d.status = _status(d, online, gb_status)
    return devices


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(device_id: int, db: AsyncSession = Depends(get_db)):
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    if device.access_type == "gb28181":
        device.status = _status(device, set(), await channel_statuses(db))
    return device


@router.put("/{device_id}", response_model=DeviceOut)
async def update_device(
    device_id: int, body: DeviceUpdate, db: AsyncSession = Depends(get_db)
):
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if changes.get("access_type", device.access_type) != device.access_type and (
        device.access_type == "gb28181" or changes.get("access_type") == "gb28181"
    ):
        raise HTTPException(409, "国标通道不能与直连设备相互转换")
    if device.access_type == "gb28181":
        allowed = {"name", "vendor", "enabled", "record_enabled"}
        if any(key not in allowed and value != getattr(device, key) for key, value in changes.items()):
            raise HTTPException(400, "国标通道只支持修改名称、厂商、启用与录像开关")
        if "record_enabled" in changes and changes["record_enabled"] != device.record_enabled:
            channel = await db.scalar(select(GbChannel).where(GbChannel.device_id == device_id))
            if channel:
                channel.record_paused = False
    for key, value in changes.items():
        setattr(device, key, value)
    await db.commit()
    await db.refresh(device)
    if not await apply_stream(device, replace=True):
        raise HTTPException(status_code=502, detail="设备配置已保存，但流媒体同步失败，请检查流媒体服务后重试")
    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(device_id: int, db: AsyncSession = Depends(get_db)):
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    if device.access_type == "gb28181":
        raise HTTPException(409, "国标通道由设备目录维护，请使用启用开关停用，历史录像会继续保留")
    await zlm.del_stream_proxy(device_id)
    await db.execute(delete(Recording).where(Recording.device_id == device_id))
    await db.delete(device)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
