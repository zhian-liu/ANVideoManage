"""Periodically remove completed recordings according to the saved retention."""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.models import Recording
from app.services.storage import get_recording_retention_days

logger = logging.getLogger(__name__)

CLEANUP_INTERVAL_SECONDS = 60 * 60
CLEANUP_BATCH_SIZE = 200


async def _recording_file_missing(recording: Recording) -> bool:
    if not recording.file_path:
        return True
    try:
        await asyncio.to_thread(Path(recording.file_path).stat)
    except FileNotFoundError:
        return True
    except OSError as exc:
        logger.warning(
            "Cannot inspect recording %s (%s); will retry: %s",
            recording.id,
            recording.file_path,
            exc,
        )
    return False


async def _cleanup_missing_recordings(db: AsyncSession) -> int:
    """Remove database indexes whose files were deleted outside the app."""
    last_id = 0
    deleted = 0
    while True:
        recordings = (
            await db.scalars(
                select(Recording)
                .where(Recording.id > last_id)
                .order_by(Recording.id)
                .limit(CLEANUP_BATCH_SIZE)
            )
        ).all()
        if not recordings:
            break
        last_id = recordings[-1].id
        for recording in recordings:
            if await _recording_file_missing(recording):
                await db.delete(recording)
                deleted += 1
        await db.commit()
    return deleted


async def cleanup_expired_recordings(
    db: AsyncSession, *, now: datetime | None = None
) -> int:
    # Recording timestamps from on_record_mp4 are stored as naive UTC.
    now = now or datetime.utcnow()
    deleted = await _cleanup_missing_recordings(db)
    retention_days = await get_recording_retention_days(db)
    if retention_days == 0:
        return deleted

    last_id = 0
    while True:
        # Re-read after each committed batch so changes also affect a long sweep.
        retention_days = await get_recording_retention_days(db)
        if retention_days == 0:
            break
        cutoff = now - timedelta(days=retention_days)
        recordings = (
            await db.scalars(
                select(Recording)
                .where(Recording.id > last_id, Recording.end_time < cutoff)
                .order_by(Recording.id)
                .limit(CLEANUP_BATCH_SIZE)
            )
        ).all()
        if not recordings:
            break
        last_id = recordings[-1].id

        # Repeated hooks can produce multiple indexes for the same file. Keep
        # the file if a more recent recording still references it.
        retained_paths = set(
            await db.scalars(
                select(Recording.file_path).where(
                    Recording.file_path.in_([rec.file_path for rec in recordings]),
                    Recording.end_time >= cutoff,
                )
            )
        )
        for recording in recordings:
            if recording.file_path and recording.file_path not in retained_paths:
                try:
                    # Use indexed paths, including old archive locations. Never
                    # scan directories that may contain snapshots/active files.
                    await asyncio.to_thread(
                        Path(recording.file_path).unlink, missing_ok=True
                    )
                except (OSError, ValueError) as exc:
                    logger.warning(
                        "Cannot remove expired recording %s (%s); will retry: %s",
                        recording.id,
                        recording.file_path,
                        exc,
                    )
                    continue
            await db.delete(recording)
            deleted += 1
        await db.commit()
    return deleted


async def run_recording_cleanup(wakeup: asyncio.Event) -> None:
    """Run at startup, after settings are saved, and hourly while running."""
    while True:
        wakeup.clear()
        try:
            async with SessionLocal() as db:
                deleted = await cleanup_expired_recordings(db)
            if deleted:
                logger.info("Removed %s expired recording indexes", deleted)
        except Exception:
            logger.exception("Recording cleanup failed; will retry")
        try:
            await asyncio.wait_for(wakeup.wait(), timeout=CLEANUP_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass
