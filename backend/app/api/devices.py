from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models import Device, Recording
from app.schemas.device import DeviceCreate, DeviceOut, DeviceUpdate
from app.services.stream_sync import apply_stream
from app.services.zlmediakit import stream_key, zlm

router = APIRouter(
    prefix="/api/devices",
    tags=["devices"],
    dependencies=[Depends(get_current_user)],
)


def _status(device: Device, online: set[str]) -> str:
    if not device.enabled:
        return "unknown"
    return "online" if stream_key(device.id) in online else "offline"


@router.post("", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
async def create_device(body: DeviceCreate, db: AsyncSession = Depends(get_db)):
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
    for d in devices:
        d.status = _status(d, online)
    return devices


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(device_id: int, db: AsyncSession = Depends(get_db)):
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    return device


@router.put("/{device_id}", response_model=DeviceOut)
async def update_device(
    device_id: int, body: DeviceUpdate, db: AsyncSession = Depends(get_db)
):
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(device, key, value)
    await db.commit()
    await db.refresh(device)
    await apply_stream(device)
    return device


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(device_id: int, db: AsyncSession = Depends(get_db)):
    device = await db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=404, detail="设备不存在")
    await zlm.del_stream_proxy(device_id)
    await db.execute(delete(Recording).where(Recording.device_id == device_id))
    await db.delete(device)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
