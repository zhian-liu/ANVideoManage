import asyncio
import errno
import tempfile
import unittest
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.settings import router as settings_router
from app.api.zlm_hook import router as hook_router
from app.core.deps import get_current_user
from app.database import Base, get_db
from app.models import AppSetting, Device, Recording
from app.services import recording_cleanup
from app.services.storage import (
    RECORDING_RETENTION_KEY,
    get_recording_retention_days,
    set_storage_values,
)


class RecordingRetentionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="video-manage-retention-")
        self.root = Path(self.temp_dir.name)
        self.now = datetime.utcnow().replace(microsecond=0)
        self.engine = create_async_engine(
            f"sqlite+aiosqlite:///{(self.root / 'test.db').as_posix()}"
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with self.sessions() as db:
            db.add(Device(id=1, name="Test camera"))
            await db.commit()

        async def test_db():
            async with self.sessions() as db:
                yield db

        self.app = FastAPI()
        self.app.include_router(settings_router)
        self.app.include_router(hook_router)
        self.app.dependency_overrides[get_db] = test_db
        self.app.dependency_overrides[get_current_user] = lambda: object()
        self.app.state.recording_cleanup_wakeup = asyncio.Event()
        self.client = AsyncClient(
            transport=ASGITransport(app=self.app), base_url="http://test"
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.engine.dispose()
        self.temp_dir.cleanup()

    async def configure(self, days):
        async with self.sessions() as db:
            await set_storage_values(
                db, str(self.root / "archive"), str(self.root / "snapshots"), days
            )

    async def add_recording(self, name, *, end=None, start=None, exists=True):
        path = self.root / name
        if exists:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"test recording")
        end = end or self.now - timedelta(days=90)
        async with self.sessions() as db:
            db.add(
                Recording(
                    device_id=1,
                    start_time=start or end - timedelta(minutes=5),
                    end_time=end,
                    file_path=str(path),
                    file_name=path.name,
                    file_size=14,
                )
            )
            await db.commit()
        return path

    async def remaining_names(self):
        async with self.sessions() as db:
            return list(await db.scalars(select(Recording.file_name)))

    async def cleanup(self):
        async with self.sessions() as db:
            return await recording_cleanup.cleanup_expired_recordings(db, now=self.now)

    async def test_default_and_disabled_cleanup_keep_old_recordings(self):
        old = await self.add_recording("old.mp4")
        self.assertEqual(await self.cleanup(), 0)
        await self.configure(7)
        await self.configure(0)
        self.assertEqual(await self.cleanup(), 0)
        self.assertTrue(old.exists())
        self.assertEqual(await self.remaining_names(), ["old.mp4"])

    async def test_expiry_uses_end_time_and_only_removes_indexed_files(self):
        await self.configure(7)
        cutoff = self.now - timedelta(days=7)
        old = await self.add_recording(
            "previous-archive/old.mp4", end=cutoff - timedelta(seconds=1)
        )
        await self.add_recording("missing.mp4", exists=False)
        boundary = await self.add_recording("boundary.mp4", end=cutoff)
        recent = await self.add_recording("recent.mp4", end=self.now)
        spanning = await self.add_recording(
            "spanning.mp4", start=cutoff - timedelta(minutes=5), end=cutoff + timedelta(minutes=5)
        )
        active = self.root / "active.mp4"
        snapshot = self.root / "snapshot.jpg"
        active.write_bytes(b"still recording")
        snapshot.write_bytes(b"snapshot")

        self.assertEqual(await self.cleanup(), 2)
        self.assertFalse(old.exists())
        for path in (boundary, recent, spanning, active, snapshot):
            self.assertTrue(path.exists(), path.name)
        self.assertCountEqual(
            await self.remaining_names(), ["boundary.mp4", "recent.mp4", "spanning.mp4"]
        )

    async def test_failed_file_is_retried_without_blocking_later_batches(self):
        await self.configure(7)
        paths = [await self.add_recording(f"old-{i}.mp4") for i in range(5)]
        original_unlink = Path.unlink

        def unlink(path, *args, **kwargs):
            if path == paths[0]:
                raise PermissionError("file in use")
            return original_unlink(path, *args, **kwargs)

        with (
            patch.object(Path, "unlink", unlink),
            patch.object(recording_cleanup, "CLEANUP_BATCH_SIZE", 2),
            self.assertLogs(recording_cleanup.logger, level="WARNING"),
        ):
            self.assertEqual(await asyncio.wait_for(self.cleanup(), timeout=5), 4)
        self.assertTrue(paths[0].exists())
        self.assertEqual(await self.remaining_names(), ["old-0.mp4"])
        self.assertEqual(await self.cleanup(), 1)
        self.assertFalse(paths[0].exists())
        self.assertEqual(await self.remaining_names(), [])

    async def test_recent_index_keeps_a_shared_file(self):
        await self.configure(7)
        shared = await self.add_recording("shared.mp4")
        await self.add_recording("shared.mp4", end=self.now)
        self.assertEqual(await self.cleanup(), 1)
        self.assertTrue(shared.exists())
        self.assertEqual(await self.remaining_names(), ["shared.mp4"])

    async def test_invalid_stored_retention_disables_deletion(self):
        old = await self.add_recording("old.mp4")
        await self.configure(0)
        for value in ("invalid", "-1", "3651", "", "1.5"):
            with self.subTest(value=value):
                async with self.sessions() as db:
                    item = await db.get(AppSetting, RECORDING_RETENTION_KEY)
                    item.value = value
                    await db.commit()
                self.assertEqual(await self.cleanup(), 0)
                self.assertTrue(old.exists())

    async def test_api_persists_retention_and_preserves_it_for_older_clients(self):
        response = await self.client.get("/api/settings")
        self.assertEqual(response.json()["recording_retention_days"], 0)
        for days in (1, 30, 3650):
            with self.subTest(days=days):
                response = await self.client.put(
                    "/api/settings/storage", json={"recording_retention_days": days}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["recording_retention_days"], days)

        await self.engine.dispose()  # Reconnect to the saved database.
        response = await self.client.get("/api/settings")
        self.assertEqual(response.json()["recording_retention_days"], 3650)
        response = await self.client.put(
            "/api/settings/storage",
            json={"recording_path": str(self.root / "new-archive"), "snapshot_path": ""},
        )
        self.assertEqual(response.json()["recording_retention_days"], 3650)
        self.assertTrue(self.app.state.recording_cleanup_wakeup.is_set())
        response = await self.client.put(
            "/api/settings/storage", json={"recording_retention_days": 0}
        )
        self.assertEqual(response.json()["recording_retention_days"], 0)
        async with self.sessions() as db:
            self.assertEqual(await get_recording_retention_days(db), 0)

    async def test_api_rejects_invalid_days_without_changing_settings(self):
        await self.configure(30)
        for value in (-1, 3651, 1.5, True, "30", None):
            with self.subTest(value=value):
                response = await self.client.put(
                    "/api/settings/storage", json={"recording_retention_days": value}
                )
                self.assertEqual(response.status_code, 422)
        response = await self.client.get("/api/settings")
        self.assertEqual(response.json()["recording_retention_days"], 30)

    async def test_saving_settings_wakes_worker_and_applies_latest_retention(self):
        old = await self.add_recording("old.mp4")
        recent = await self.add_recording("recent.mp4", end=self.now)
        cycles = asyncio.Queue()
        actual_cleanup = recording_cleanup.cleanup_expired_recordings

        async def observe(db):
            deleted = await actual_cleanup(db, now=self.now)
            cycles.put_nowait(deleted)
            return deleted

        with (
            patch.object(recording_cleanup, "SessionLocal", self.sessions),
            patch.object(recording_cleanup, "cleanup_expired_recordings", observe),
        ):
            task = asyncio.create_task(
                recording_cleanup.run_recording_cleanup(self.app.state.recording_cleanup_wakeup)
            )
            try:
                self.assertEqual(await asyncio.wait_for(cycles.get(), timeout=5), 0)
                self.assertTrue(old.exists())
                response = await self.client.put(
                    "/api/settings/storage", json={"recording_retention_days": 7}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(await asyncio.wait_for(cycles.get(), timeout=5), 1)
                self.assertFalse(old.exists())
                self.assertTrue(recent.exists())
                await self.client.put(
                    "/api/settings/storage", json={"recording_retention_days": 0}
                )
                self.assertEqual(await asyncio.wait_for(cycles.get(), timeout=5), 0)
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    async def test_worker_retries_after_error_on_next_interval(self):
        retried = asyncio.Event()
        calls = 0

        async def sweep(db):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("temporary database failure")
            retried.set()
            return 0

        with (
            patch.object(recording_cleanup, "SessionLocal", self.sessions),
            patch.object(recording_cleanup, "cleanup_expired_recordings", sweep),
            patch.object(recording_cleanup, "CLEANUP_INTERVAL_SECONDS", 0.01),
            self.assertLogs(recording_cleanup.logger, level="ERROR"),
        ):
            task = asyncio.create_task(recording_cleanup.run_recording_cleanup(asyncio.Event()))
            try:
                await asyncio.wait_for(retried.wait(), timeout=5)
                self.assertGreaterEqual(calls, 2)
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    async def test_lifespan_starts_and_stops_worker(self):
        from app import main

        started = asyncio.Event()
        stopped = asyncio.Event()
        policy_started = asyncio.Event()
        policy_stopped = asyncio.Event()

        async def worker(wakeup):
            self.assertIs(wakeup, self.app.state.recording_cleanup_wakeup)
            started.set()
            try:
                await asyncio.Future()
            finally:
                stopped.set()

        async def policy():
            policy_started.set()
            try:
                await asyncio.Future()
            finally:
                policy_stopped.set()

        with (
            patch.object(main, "engine", self.engine),
            patch.object(main, "SessionLocal", self.sessions),
            patch.object(main, "_ensure_sqlite_dir"),
            patch.object(main, "hash_password", return_value="test-hash"),
            patch.object(main, "run_recording_cleanup", worker),
            patch.object(main, "run_recording_policy", policy),
        ):
            async with main.lifespan(self.app):
                await asyncio.wait_for(started.wait(), timeout=5)
                await asyncio.wait_for(policy_started.wait(), timeout=5)
            self.assertTrue(stopped.is_set())
            self.assertTrue(policy_stopped.is_set())

    async def test_cross_volume_archive_and_cleanup_leave_no_source_copy(self):
        await self.configure(7)
        source = self.root / "zlm-segment.mp4"
        source.write_bytes(b"completed segment")
        start = self.now - timedelta(days=8)
        cross_volume = OSError(errno.EXDEV, "Cross-device link")
        with (
            patch.object(Path, "replace", side_effect=cross_volume),
            patch("shutil.os.rename", side_effect=cross_volume),
        ):
            response = await self.client.post(
                "/api/zlm/hook/on_record_mp4",
                json={
                    "stream": "device_1",
                    "start_time": start.replace(tzinfo=timezone.utc).timestamp(),
                    "time_len": 300,
                    "file_path": str(source),
                    "file_name": source.name,
                    "file_size": source.stat().st_size,
                },
            )
        self.assertEqual(response.status_code, 200)
        async with self.sessions() as db:
            recording = (await db.scalars(select(Recording))).one()
            archived = Path(recording.file_path)
            self.assertEqual(recording.end_time, start + timedelta(seconds=300))
        self.assertFalse(source.exists())
        self.assertEqual(archived.read_bytes(), b"completed segment")
        self.assertEqual(await self.cleanup(), 1)
        self.assertFalse(archived.exists())
        self.assertEqual(await self.remaining_names(), [])


if __name__ == "__main__":
    unittest.main()
