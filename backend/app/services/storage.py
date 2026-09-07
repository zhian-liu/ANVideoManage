"""Application storage settings and filesystem helpers."""

import asyncio
import os
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AppSetting

RECORDING_KEY = "recording_path"
SNAPSHOT_KEY = "snapshot_path"
RECORDING_RETENTION_KEY = "recording_retention_days"


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


async def get_recording_retention_days(db: AsyncSession) -> int:
    """Zero (including missing/invalid settings) keeps recordings forever."""
    value = await _get_value(db, RECORDING_RETENTION_KEY, "0")
    try:
        days = int(value)
    except ValueError:
        return 0
    return days if 0 <= days <= 3650 else 0


def _directory_roots() -> list[Path]:
    if os.name == "nt":
        import ctypes

        drives = ctypes.windll.kernel32.GetLogicalDrives()
        return [Path(f"{chr(65 + i)}:/") for i in range(26) if drives & (1 << i)]
    return [Path("/")]


def browse_storage_directories(path: str = "") -> dict:
    """List one level on the storage host; never return file contents."""
    if "\x00" in path:
        raise ValueError("路径不能包含空字符")
    if not path.strip():
        return {
            "current_path": "",
            "parent_path": None,
            "directories": [{"name": str(root), "path": str(root)} for root in _directory_roots()],
        }

    current = _absolute_path(path.strip())
    directories = []
    with os.scandir(current) as entries:
        for entry in entries:
            try:
                if entry.is_dir():
                    directories.append({"name": entry.name, "path": str(current / entry.name)})
            except OSError:
                continue
    directories.sort(key=lambda entry: (entry["name"].casefold(), entry["name"]))
    return {
        "current_path": str(current),
        "parent_path": str(current.parent) if current.parent != current else "",
        "directories": directories,
    }


async def set_storage_values(
    db: AsyncSession,
    recording_path: str,
    snapshot_path: str,
    recording_retention_days: int | None = None,
) -> tuple[str, str]:
    values = {RECORDING_KEY: recording_path, SNAPSHOT_KEY: snapshot_path}
    if recording_retention_days is not None:
        values[RECORDING_RETENTION_KEY] = str(recording_retention_days)
    for key, value in values.items():
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
    """Move a completed ZLMediaKit segment into the configured archive root.

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

    def _move() -> None:
        if not source.is_file():
            return
        try:
            source.replace(target)
        except OSError:
            import shutil

            shutil.move(str(source), str(target))

    await asyncio.to_thread(_move)
    return str(target) if target.exists() else source_path
