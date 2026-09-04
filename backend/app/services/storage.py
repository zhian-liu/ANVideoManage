"""Application storage settings and filesystem helpers."""

import asyncio
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AppSetting

RECORDING_KEY = "recording_path"
SNAPSHOT_KEY = "snapshot_path"


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _absolute_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = _backend_root() / path
    return path.resolve()


def default_recording_path() -> str:
    return settings.recording_path


def default_snapshot_path() -> str:
    return settings.snapshot_path


async def _get_value(db: AsyncSession, key: str, default: str) -> str:
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    item = result.scalar_one_or_none()
    return item.value if item is not None else default


async def get_storage_values(db: AsyncSession) -> tuple[str, str]:
    return (
        await _get_value(db, RECORDING_KEY, default_recording_path()),
        await _get_value(db, SNAPSHOT_KEY, default_snapshot_path()),
    )


async def set_storage_values(
    db: AsyncSession, recording_path: str, snapshot_path: str
) -> tuple[str, str]:
    for key, value in (
        (RECORDING_KEY, recording_path),
        (SNAPSHOT_KEY, snapshot_path),
    ):
        result = await db.execute(select(AppSetting).where(AppSetting.key == key))
        item = result.scalar_one_or_none()
        if item is None:
            db.add(AppSetting(key=key, value=value))
        else:
            item.value = value
    await db.commit()
    return recording_path, snapshot_path


async def save_snapshot(
    db: AsyncSession, device_id: int, data: bytes
) -> tuple[str, str]:
    _, configured_path = await get_storage_values(db)
    root = _absolute_path(configured_path or default_snapshot_path())
    now = datetime.now()
    directory = root / now.strftime("%Y-%m-%d")
    file_name = f"device_{device_id}_{now.strftime('%Y%m%d_%H%M%S_%f')}.jpg"
    path = directory / file_name
    await asyncio.to_thread(directory.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(path.write_bytes, data)
    return str(path), file_name


async def archive_recording(
    db: AsyncSession,
    source_path: str,
    file_name: str,
    stream: str,
    start_time: datetime,
) -> str:
    """Copy a completed ZLMediaKit segment into the configured archive root.

    An empty recording path keeps the original ZLMediaKit path untouched.
    """
    configured_path, _ = await get_storage_values(db)
    if not configured_path:
        return source_path

    source = Path(source_path)
    if not source.is_absolute():
        source = source.resolve()
    root = _absolute_path(configured_path)
    target = root / settings.zlm_app / stream / start_time.strftime("%Y-%m-%d") / (
        file_name or source.name
    )
    await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)

    def _copy() -> None:
        if not source.is_file():
            return
        try:
            source.replace(target)
        except OSError:
            import shutil

            shutil.copy2(source, target)

    await asyncio.to_thread(_copy)
    return str(target) if target.exists() else source_path
