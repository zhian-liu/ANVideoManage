"""Persistent registration/catalog state. Media sessions are managed separately."""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSetting, Device, GbChannel, GbDevice
from app.schemas.gb28181 import GbConfig, GbDeviceOut
from app.services.gb_protocol import GbMessage

CONFIG_KEY = "gb28181"


async def read_config(db: AsyncSession) -> GbConfig:
    setting = await db.get(AppSetting, CONFIG_KEY)
    return GbConfig.model_validate_json(setting.value) if setting else GbConfig()


async def write_config(db: AsyncSession, config: GbConfig) -> None:
    setting = await db.get(AppSetting, CONFIG_KEY)
    if setting is None:
        setting = AppSetting(key=CONFIG_KEY)
        db.add(setting)
    setting.value = config.model_dump_json()
    await db.commit()


def device_online(device: GbDevice, config: GbConfig, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    return bool(
        config.enabled and device.enabled and device.registered_until
        and device.registered_until > now and device.last_heartbeat
        and device.last_heartbeat + timedelta(seconds=config.heartbeat_timeout) > now
    )


def channel_online(channel: GbChannel, device: GbDevice, config: GbConfig) -> bool:
    return device_online(device, config) and channel.present and channel.status in {"ON", "ONLINE", "OK"}


def device_out(device: GbDevice, config: GbConfig) -> GbDeviceOut:
    return GbDeviceOut(
        **{key: getattr(device, key) for key in GbDeviceOut.model_fields if key != "online"},
        online=device_online(device, config),
    )


async def channel_statuses(db: AsyncSession) -> dict[int, str]:
    config = await read_config(db)
    rows = await db.execute(select(GbChannel, GbDevice).join(GbDevice, GbChannel.gb_device_id == GbDevice.id))
    return {
        channel.device_id: "online" if channel_online(channel, parent, config) else "offline"
        for channel, parent in rows if channel.device_id is not None
    }


async def apply_catalog(db: AsyncSession, device: GbDevice, message: GbMessage) -> None:
    if device.catalog_sn != message.sn or device.catalog_state != "syncing":
        return  # Duplicate completed query or delayed response from an older SN.
    expected, items = message.catalog()
    if device.catalog_expected is not None and device.catalog_expected != expected:
        raise ValueError("同一 SN 的目录 SumNum 不一致")
    existing = list(await db.scalars(select(GbChannel).where(GbChannel.gb_device_id == device.id)))
    channels = {channel.channel_id: channel for channel in existing}
    for item in items:
        channel = channels.get(item.id)
        if channel is None:
            channel = GbChannel(gb_device_id=device.id, channel_id=item.id)
            db.add(channel)
            channels[item.id] = channel
        channel.name = item.name
        channel.manufacturer = item.manufacturer
        channel.parent_id = item.parent_id
        channel.status = item.status
        channel.catalog_sn = message.sn
        channel.updated_at = datetime.utcnow()
        if item.is_video and channel.device_id is None:
            playable = Device(
                name=item.name, vendor=item.manufacturer[:64], access_type="gb28181",
                ip=device.remote_ip, port=0, onvif_port=0, record_enabled=False,
            )
            db.add(playable)
            await db.flush()
            channel.device_id = playable.id
    received = sum(channel.catalog_sn == message.sn for channel in channels.values())
    if received > expected:
        raise ValueError("目录唯一条目数超过 SumNum")
    device.catalog_expected = expected
    device.catalog_received = received
    if received == expected:
        for channel in channels.values():
            channel.present = channel.catalog_sn == message.sn
        device.catalog_state = "complete"
        device.last_error = ""
    await db.commit()
