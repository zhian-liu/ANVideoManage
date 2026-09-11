"""GB/T28181 administration; credentials are accepted only on write."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_roles
from app.database import get_db
from app.models import Device, GbChannel, GbDevice
from app.schemas.gb28181 import GbConfig, GbDeviceCreate, GbDeviceOut, GbDeviceUpdate
from app.services.gb_catalog import channel_online, device_out, read_config, write_config
from app.services.gb_gateway import GatewayError, binary_path
from app.services.gb_runtime import GbError, gb_runtime

router = APIRouter(prefix="/api/gb28181", tags=["gb28181"], dependencies=[Depends(get_current_user)])
admin = require_roles("admin")


async def config_response(db: AsyncSession):
    return {"config": await read_config(db), "service": {
        "state": gb_runtime.status, "ready": gb_runtime.ready,
        "error": gb_runtime.last_error, "binary_available": binary_path().is_file(),
    }}


@router.get("/config")
async def get_config(db: AsyncSession = Depends(get_db)):
    return await config_response(db)


@router.put("/config", dependencies=[Depends(admin)])
async def save_config(body: GbConfig, db: AsyncSession = Depends(get_db)):
    if body.enabled:
        try:
            gb_runtime.gateway.preflight()
        except GatewayError as exc:
            raise GbError(str(exc), 503) from exc
        if await db.get(GbDevice, body.sip_id) is not None:
            raise HTTPException(409, "平台编码不能与已预置的注册设备编码相同")
    await write_config(db, body)
    await gb_runtime.configure(body)
    return await config_response(db)


@router.get("/devices", response_model=list[GbDeviceOut])
async def list_gb_devices(db: AsyncSession = Depends(get_db)):
    config = await read_config(db)
    return [device_out(item, config) for item in await db.scalars(select(GbDevice).order_by(GbDevice.id))]


async def synchronize_credentials():
    try:
        await gb_runtime.sync_credentials()
    except GatewayError as exc:
        raise GbError("设备配置已保存，但下发 SIP 凭据失败，请检查国标服务后重试") from exc


@router.post("/devices", response_model=GbDeviceOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(admin)])
async def create_gb_device(body: GbDeviceCreate, db: AsyncSession = Depends(get_db)):
    config = await read_config(db)
    if body.id == config.sip_id:
        raise HTTPException(409, "设备编码不能与平台编码相同")
    if await db.get(GbDevice, body.id) is not None:
        raise HTTPException(409, "该国标设备编码已存在")
    device = GbDevice(**body.model_dump())
    db.add(device)
    await db.commit()
    await db.refresh(device)
    await synchronize_credentials()
    return device_out(device, config)


@router.put("/devices/{device_id}", response_model=GbDeviceOut, dependencies=[Depends(admin)])
async def update_gb_device(device_id: str, body: GbDeviceUpdate, db: AsyncSession = Depends(get_db)):
    device = await db.get(GbDevice, device_id)
    if device is None:
        raise HTTPException(404, "国标设备不存在")
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if ("password" in changes and changes["password"] != device.password) or changes.get("enabled") is False:
        device.registered_until = None
    for key, value in changes.items():
        setattr(device, key, value)
    await db.commit()
    await db.refresh(device)
    await synchronize_credentials()
    await gb_runtime.maintain()
    return device_out(device, await read_config(db))


@router.post("/devices/{device_id}/catalog", dependencies=[Depends(admin)])
async def sync_catalog(device_id: str):
    return {"ok": True, "sn": await gb_runtime.query_catalog(device_id)}


@router.get("/devices/{device_id}/channels")
async def list_channels(device_id: str, db: AsyncSession = Depends(get_db)):
    parent = await db.get(GbDevice, device_id)
    if parent is None:
        raise HTTPException(404, "国标设备不存在")
    config = await read_config(db)
    rows = await db.execute(select(GbChannel, Device).outerjoin(Device, Device.id == GbChannel.device_id)
                            .where(GbChannel.gb_device_id == device_id).order_by(GbChannel.channel_id))
    return [{
        "id": channel.id, "channel_id": channel.channel_id, "device_id": channel.device_id,
        "name": channel.name, "manufacturer": channel.manufacturer, "parent_id": channel.parent_id,
        "status": channel.status, "present": channel.present,
        "online": channel_online(channel, parent, config),
        "enabled": device.enabled if device else False,
        "record_enabled": device.record_enabled if device else False,
    } for channel, device in rows]
