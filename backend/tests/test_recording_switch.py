import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import devices, recordings, streams
from app.core.deps import get_current_user
from app.database import Base, get_db
from app.models import Device, Recording
from app.services import stream_sync


class FakeMediaServer:
    """Model ZLM's create-only proxies and their recording options on reconnect."""
    def __init__(self):
        self.proxies = {}
        self.recording = set()
        self.fail_changes = False
        self.starts = 0

    async def add_stream_proxy(self, device_id, url, enable_mp4=False):
        if device_id in self.proxies:
            return False
        self.proxies[device_id] = enable_mp4
        self.reconnect(device_id)
        return True

    def reconnect(self, device_id):
        self.recording.discard(device_id)
        if self.proxies[device_id]:
            self.recording.add(device_id)

    async def del_stream_proxy(self, device_id):
        if self.fail_changes:
            return False
        self.proxies.pop(device_id, None)
        self.recording.discard(device_id)
        return True

    async def stop_record(self, device_id):
        if self.fail_changes:
            return False
        self.recording.discard(device_id)
        return True

    async def start_record(self, device_id):
        self.starts += 1
        self.recording.add(device_id)
        return True

    async def is_recording(self, device_id):
        return device_id in self.recording

    async def online_streams(self):
        return {f"device_{device_id}" for device_id in self.proxies}


class RecordingSwitchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.media = FakeMediaServer()
        adapter = SimpleNamespace(resolve_stream=AsyncMock(return_value="rtsp://test.invalid/live"))
        self.patches = [
            patch.object(module, "zlm", self.media) for module in (stream_sync, devices, streams)
        ] + [
            patch.object(module, "get_adapter", return_value=adapter) for module in (stream_sync, streams)
        ] + [patch.object(stream_sync, "SessionLocal", self.sessions)]
        for item in self.patches:
            item.start()

        async def test_db():
            async with self.sessions() as db:
                yield db

        self.app = FastAPI()
        for router in (devices.router, streams.router, recordings.router):
            self.app.include_router(router)
        self.app.dependency_overrides[get_db] = test_db
        self.app.dependency_overrides[get_current_user] = lambda: object()
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        for item in reversed(self.patches):
            item.stop()
        await self.engine.dispose()

    async def add_device(self, *, record_enabled=True, enabled=True, proxy_recording=True):
        async with self.sessions() as db:
            db.add(Device(id=1, name="Test camera", record_enabled=record_enabled, enabled=enabled))
            await db.commit()
        await self.media.add_stream_proxy(1, "rtsp://test.invalid/live", proxy_recording)

    async def test_new_device_does_not_record_by_default(self):
        response = await self.client.post("/api/devices", json={"name": "New camera"})
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()["record_enabled"])
        self.assertFalse(await self.media.is_recording(response.json()["id"]))

    async def test_disabling_replaces_existing_proxy_and_stays_off_after_reconnect(self):
        await self.add_device()
        now = datetime.utcnow()
        async with self.sessions() as db:
            db.add(Recording(device_id=1, start_time=now - timedelta(minutes=10), end_time=now, file_name="history.mp4"))
            await db.commit()
        response = await self.client.put("/api/devices/1", json={"record_enabled": False})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["record_enabled"])
        self.assertFalse(await self.media.is_recording(1))
        self.media.reconnect(1)
        self.assertFalse(await self.media.is_recording(1))
        history = await self.client.get("/api/recordings")
        self.assertEqual([item["file_name"] for item in history.json()], ["history.mp4"])

    async def test_disabled_recording_rejects_manual_start(self):
        await self.add_device(record_enabled=False, proxy_recording=False)
        response = await self.client.post("/api/streams/1/record/start")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.media.starts, 0)
        self.assertFalse(await self.media.is_recording(1))

    async def test_disabled_device_rejects_stream_and_record_start(self):
        await self.add_device(enabled=False, proxy_recording=False)
        for path in ("/api/streams/1/start", "/api/streams/1/record/start"):
            response = await self.client.post(path)
            self.assertEqual(response.status_code, 403)
        self.assertEqual(self.media.starts, 0)

    async def test_enabling_and_manual_stop_start_work(self):
        await self.add_device(record_enabled=False, proxy_recording=False)
        response = await self.client.put("/api/devices/1", json={"record_enabled": True})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(await self.media.is_recording(1))
        response = await self.client.post("/api/streams/1/record/stop")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(await self.media.is_recording(1))
        response = await self.client.post("/api/streams/1/record/start")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(await self.media.is_recording(1))

    async def test_failed_sync_does_not_report_success(self):
        await self.add_device()
        self.media.fail_changes = True
        response = await self.client.put("/api/devices/1", json={"record_enabled": False})
        self.assertEqual(response.status_code, 502)
        async with self.sessions() as db:
            self.assertFalse((await db.get(Device, 1)).record_enabled)
        self.media.fail_changes = False
        await stream_sync.reconcile_disabled_recordings()
        self.assertFalse(await self.media.is_recording(1))

    async def test_policy_repairs_legacy_recording_without_an_open_browser(self):
        await self.add_device(record_enabled=False, proxy_recording=True)
        await stream_sync.reconcile_disabled_recordings()
        self.assertFalse(await self.media.is_recording(1))
        self.media.reconnect(1)
        self.assertFalse(await self.media.is_recording(1))

    async def test_policy_rechecks_a_switch_changed_during_network_requests(self):
        await self.add_device(record_enabled=False, proxy_recording=True)

        async def changed_while_checking(device_id):
            async with self.sessions() as db:
                device = await db.get(Device, device_id)
                device.record_enabled = True
                await db.commit()
            return True

        with patch.object(self.media, "is_recording", changed_while_checking):
            await stream_sync.reconcile_disabled_recordings()
        self.assertTrue(await self.media.is_recording(1))
        self.assertTrue(self.media.proxies[1])

    async def test_stream_info_repairs_stale_recording_state(self):
        await self.add_device(record_enabled=False, proxy_recording=True)
        response = await self.client.get("/api/streams/1")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["recording"])
        self.assertTrue(response.json()["online"])
