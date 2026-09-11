import asyncio
import base64
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api import devices, gb28181, streams, zlm_hook
from app.core.deps import get_current_user
from app.database import Base, get_db
from app.models import Device, GbChannel, GbDevice, GbStreamSession
from app.schemas.gb28181 import GbConfig
from app.services import gb_runtime as runtime_module
from app.services.gb_catalog import apply_catalog, write_config
from app.services.gb_protocol import make_live_sdp, parse_message, validate_answer
from app.services.gb_runtime import GbError, GbRuntime

DEVICE = "34020000001180000001"
CHANNEL = "34020000001320000001"
CHANNEL2 = "34020000001320000002"


def catalog(sn, total, items, device=DEVICE, encoding="utf-8"):
    entries = "".join(f"<Item><DeviceID>{code}</DeviceID><Name>{name}</Name><Status>ON</Status></Item>" for code, name in items)
    return (f'<?xml version="1.0" encoding="{encoding}"?><Response><CmdType>Catalog</CmdType><SN>{sn}</SN>'
            f'<DeviceID>{device}</DeviceID><SumNum>{total}</SumNum><DeviceList Num="{len(items)}">{entries}</DeviceList></Response>').encode(encoding)


class Media:
    def __init__(self):
        self.receivers = {}
        self.online = set()
        self.recording = set()
        self.opens = 0
        self.closes = 0
        self.fail_close = False

    async def open_rtp_server(self, device_id, ssrc, tcp=False):
        if device_id in self.receivers:
            raise RuntimeError("duplicate receiver")
        self.opens += 1
        self.receivers[device_id] = {"ssrc": ssrc, "tcp": tcp}
        return 32000 + 2 * device_id

    async def close_rtp_server(self, device_id):
        if self.fail_close:
            raise RuntimeError("media server unavailable")
        self.closes += 1
        self.receivers.pop(device_id, None)
        self.online.discard(device_id)
        self.recording.discard(device_id)

    async def online_streams(self):
        return {f"device_{device_id}" for device_id in self.online}

    async def start_record(self, device_id):
        if device_id not in self.online:
            return False
        self.recording.add(device_id)
        return True

    async def stop_record(self, device_id):
        self.recording.discard(device_id)
        return True

    async def is_recording(self, device_id):
        return device_id in self.recording


class Gateway:
    def __init__(self, media):
        self.running = True
        self.instance = "test-instance"
        self.runtime = None
        self.media = media
        self.commands = []
        self.send_media = True
        self.reject = False

    def preflight(self):
        pass

    async def start(self, config):
        self.running = True

    async def stop(self):
        self.running = False

    async def call(self, method, path, **kwargs):
        self.commands.append((method, path, kwargs))
        if path == "/v1/events":
            return {"instance": self.instance, "events": [], "latest": 0, "gap": False}
        if path == "/v1/invite":
            command = kwargs["json"]
            if self.send_media and not self.reject:
                self.media.online.add(1)
            answer = command["sdp"].replace("a=recvonly", "a=sendonly").replace("a=setup:passive", "a=setup:active")
            await self.runtime.handle_event({"type": "session", "session_id": command["session_id"],
                "state": "failed" if self.reject else "established", "sdp": answer, "reason": "SIP 486"})
            return {"call_id": "test-call"}
        return {"ok": True}


class ProtocolTests(unittest.TestCase):
    def test_gb2312_chinese_and_video_vs_directory_classification(self):
        message = parse_message(catalog(1, 2, [(CHANNEL, "门口摄像机"), ("340200", "区域")], encoding="gb2312"), DEVICE)
        total, items = message.catalog()
        self.assertEqual(total, 2)
        self.assertEqual(items[0].name, "门口摄像机")
        self.assertTrue(items[0].is_video)
        self.assertFalse(items[1].is_video)

    def test_rejects_entities_spoofed_identity_and_oversized_xml(self):
        for payload in (b'<!DOCTYPE a [<!ENTITY e "boom">]><a/>', catalog(1, 0, [], device=CHANNEL), b'x' * (256 * 1024 + 1)):
            with self.subTest(payload=payload[:30]):
                with self.assertRaises(ValueError):
                    parse_message(payload, DEVICE)

    def test_tcp_answer_must_accept_ps_and_active_connection(self):
        config = GbConfig(enabled=True, advertise_ip="127.0.0.1", media_ip="127.0.0.1", media_transport="tcp-passive")
        offer = make_live_sdp(config, CHANNEL, 30000, 200000001)
        answer = offer.replace("a=recvonly", "a=sendonly").replace("a=setup:passive", "a=setup:active")
        validate_answer(answer, "tcp-passive", 200000001)
        for invalid in (offer, answer.replace("PS/90000", "H264/90000"), answer.replace("m=video 30000", "m=video 0"), answer.replace("0200000001", "0200000002")):
            with self.assertRaises(ValueError):
                validate_answer(invalid, "tcp-passive", 200000001)


class GbBusinessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gb-business-")
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{(Path(self.temp.name) / 'test.db').as_posix()}")
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.config = GbConfig(enabled=True, advertise_ip="127.0.0.1", media_ip="127.0.0.1",
                               invite_timeout=3, media_timeout=3, heartbeat_timeout=10)
        self.media = Media()
        self.gateway = Gateway(self.media)
        self.runtime = GbRuntime(self.sessions, self.media, self.gateway)
        self.gateway.runtime = self.runtime
        self.runtime.config = self.config
        self.runtime.status = "running"
        now = datetime.utcnow()
        async with self.sessions() as db:
            db.add(GbDevice(id=DEVICE, name="NVR", password="not-in-responses", registered_until=now + timedelta(hours=1), last_heartbeat=now))
            db.add(Device(id=1, name="Original", access_type="gb28181"))
            await db.flush()
            db.add(GbChannel(gb_device_id=DEVICE, channel_id=CHANNEL, device_id=1, name="Original"))
            await db.commit()
            await write_config(db, self.config)
        self.app = FastAPI()
        for router in (gb28181.router, devices.router, streams.router, zlm_hook.router):
            self.app.include_router(router)
        async def db_dependency():
            async with self.sessions() as db:
                yield db
        self.app.dependency_overrides[get_db] = db_dependency
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1, role="admin")
        self.patches = [patch.object(module, "gb_runtime", self.runtime) for module in (gb28181, streams, runtime_module)]
        self.patches += [patch.object(module, "zlm", self.media) for module in (devices, streams)]
        for item in self.patches:
            item.start()
        self.client = AsyncClient(transport=ASGITransport(app=self.app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.media.fail_close = False
        await self.runtime.close()
        for item in reversed(self.patches):
            item.stop()
        await self.engine.dispose()
        self.temp.cleanup()

    async def get(self, model, key):
        async with self.sessions() as db:
            return await db.get(model, key)

    async def wait_jobs(self):
        await asyncio.gather(*list(self.runtime.jobs.values()))

    async def apply(self, raw):
        async with self.sessions() as db:
            device = await db.get(GbDevice, DEVICE)
            await apply_catalog(db, device, parse_message(raw, DEVICE))

    async def begin_catalog(self, sn=10):
        async with self.sessions() as db:
            device = await db.get(GbDevice, DEVICE)
            device.catalog_sn, device.catalog_state = sn, "syncing"
            device.catalog_expected, device.catalog_received = None, 0
            device.catalog_started_at = datetime.utcnow()
            await db.commit()

    async def test_catalog_batches_duplicates_and_complete_pruning_preserve_devices(self):
        await self.begin_catalog()
        await self.apply(catalog(10, 2, [(CHANNEL2, "Second")]))
        old = await self.get(GbChannel, 1)
        self.assertTrue(old.present)
        self.assertEqual((await self.get(GbDevice, DEVICE)).catalog_received, 1)
        await self.apply(catalog(10, 2, [(CHANNEL2, "Second")]))
        self.assertEqual((await self.get(GbDevice, DEVICE)).catalog_received, 1)
        await self.apply(catalog(9, 0, []))
        self.assertTrue((await self.get(GbChannel, 1)).present)
        await self.apply(catalog(10, 2, [("340200", "Area")]))
        self.assertEqual((await self.get(GbDevice, DEVICE)).catalog_state, "complete")
        self.assertFalse((await self.get(GbChannel, 1)).present)
        self.assertIsNotNone(await self.get(Device, 1))
        async with self.sessions() as db:
            self.assertEqual(await db.scalar(select(func.count()).select_from(Device)), 2)
            node = await db.scalar(select(GbChannel).where(GbChannel.channel_id == "340200"))
            self.assertIsNone(node.device_id)

    async def test_invalid_catalog_does_not_delete_old_channels(self):
        await self.begin_catalog()
        await self.apply(catalog(10, 2, [(CHANNEL2, "Second")]))
        raw = catalog(10, 3, [("340200", "Area")])
        await self.runtime.handle_event({"type": "message", "device_id": DEVICE, "time": int(time.time()), "body_base64": base64.b64encode(raw).decode()})
        self.assertEqual((await self.get(GbDevice, DEVICE)).catalog_state, "error")
        self.assertTrue((await self.get(GbChannel, 1)).present)

    async def test_online_status_is_registration_not_presence_of_media(self):
        response = await self.client.get("/api/devices")
        self.assertEqual(response.json()[0]["status"], "online")
        self.assertFalse(self.media.online)
        await self.client.post("/api/zlm/hook/on_stream_changed", json={"stream": "device_1", "regist": False})
        response = await self.client.get("/api/devices/1")
        self.assertEqual(response.json()["status"], "online")

    async def test_credentials_are_write_only_and_mutations_need_admin(self):
        response = await self.client.get("/api/gb28181/devices")
        self.assertNotIn("password", response.json()[0])
        self.assertNotIn("not-in-responses", response.text)
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=2, role="viewer")
        response = await self.client.put(f"/api/gb28181/devices/{DEVICE}", json={"enabled": False})
        self.assertEqual(response.status_code, 403)
        self.assertTrue((await self.get(GbDevice, DEVICE)).enabled)

    async def test_gb_channels_cannot_be_created_or_converted_by_direct_crud(self):
        response = await self.client.post("/api/devices", json={"name": "fake", "access_type": "gb28181"})
        self.assertEqual(response.status_code, 400)
        response = await self.client.put("/api/devices/1", json={"access_type": "onvif"})
        self.assertEqual(response.status_code, 409)
        response = await self.client.delete("/api/devices/1")
        self.assertEqual(response.status_code, 409)

    async def test_concurrent_viewers_share_one_invite_and_release_only_their_lease(self):
        first, second = await asyncio.gather(self.runtime.acquire_lease(1, 1, None), self.runtime.acquire_lease(1, 2, None))
        self.assertEqual(self.media.opens, 1)
        self.assertEqual(sum(path == "/v1/invite" for _, path, _ in self.gateway.commands), 1)
        with self.assertRaises(GbError) as caught:
            await self.runtime.release_lease(1, 3, first["lease_id"])
        self.assertEqual(caught.exception.status_code, 403)
        await self.runtime.release_lease(1, 1, first["lease_id"])
        self.assertIn(1, self.media.receivers)
        await self.runtime.release_lease(1, 2, second["lease_id"])
        self.assertNotIn(1, self.media.receivers)
        self.assertIsNone(await self.get(GbStreamSession, 1))

    async def test_media_timeout_releases_sip_and_rtp_and_failed_lease(self):
        self.gateway.send_media = False
        with self.assertRaises(GbError) as caught:
            await self.runtime.acquire_lease(1, 1, None)
        self.assertIn("未收到", caught.exception.detail)
        self.assertFalse(self.media.receivers)
        self.assertFalse(self.runtime.viewers(1))
        self.assertIsNone(await self.get(GbStreamSession, 1))
        self.assertTrue(any(method == "DELETE" for method, _, _ in self.gateway.commands))

    async def test_returned_lease_has_full_ttl_after_slow_media_and_collection(self):
        clock = SimpleNamespace(now=100.0)
        original_info = self.runtime.stream_info

        async def delayed_info(device_id):
            clock.now += 200
            self.assertFalse(self.runtime.viewers(device_id))
            return await original_info(device_id)

        with patch.object(runtime_module, "time", SimpleNamespace(monotonic=lambda: clock.now)):
            with patch.object(self.runtime, "stream_info", side_effect=delayed_info):
                lease = await self.runtime.acquire_lease(1, 1, None)
            self.assertTrue(self.runtime.viewers(1))
            self.assertEqual(self.runtime.leases[1][lease["lease_id"]][1] - clock.now, lease["expires_in"])
            clock.now += 15
            renewed = await self.runtime.acquire_lease(1, 1, lease["lease_id"])
            self.assertEqual(renewed["lease_id"], lease["lease_id"])
            self.assertEqual(self.media.opens, 1)

    async def test_sip_rejection_and_cleanup_failure_keep_recoverable_intent(self):
        self.gateway.reject = True
        self.media.fail_close = True
        with self.assertRaises(GbError):
            await self.runtime.acquire_lease(1, 1, None)
        self.assertEqual((await self.get(GbStreamSession, 1)).state, "cleanup")
        self.media.fail_close = False
        await self.runtime.stop_stream(1)
        self.assertFalse(self.media.receivers)
        self.assertIsNone(await self.get(GbStreamSession, 1))

    async def test_heartbeat_timeout_stops_even_with_live_viewer_lease(self):
        await self.runtime.acquire_lease(1, 1, None)
        async with self.sessions() as db:
            device = await db.get(GbDevice, DEVICE)
            device.last_heartbeat = datetime.utcnow() - timedelta(seconds=11)
            await db.commit()
        await self.runtime.maintain()
        await self.wait_jobs()
        self.assertFalse(self.media.receivers)
        response = await self.client.get("/api/devices")
        self.assertEqual(response.json()[0]["status"], "offline")

    async def test_manual_record_stop_remains_stopped_and_recording_keeps_stream(self):
        async with self.sessions() as db:
            device = await db.get(Device, 1)
            device.record_enabled = True
            await db.commit()
        lease = await self.runtime.acquire_lease(1, 1, None)
        self.assertTrue(await self.media.is_recording(1))
        await self.runtime.release_lease(1, 1, lease["lease_id"])
        self.assertIn(1, self.media.receivers)
        await self.runtime.set_recording(1, False)
        await self.runtime.maintain()
        await self.wait_jobs()
        self.assertFalse(self.media.receivers)
        self.assertTrue((await self.get(GbChannel, 1)).record_paused)

    async def test_restart_cleans_persisted_receiver_and_waits_for_reregistration(self):
        await self.runtime.acquire_lease(1, 1, None)
        await self.runtime.configure(self.config)
        self.assertFalse(self.media.receivers)
        self.assertIsNone((await self.get(GbDevice, DEVICE)).registered_until)
        self.assertIsNone(await self.get(GbStreamSession, 1))

    async def test_config_database_failure_does_not_leave_service_changing(self):
        with patch.object(self.runtime, "mark_offline", side_effect=RuntimeError("database unavailable")):
            with self.assertRaises(GbError):
                await self.runtime.configure(self.config)
        self.assertFalse(self.runtime.changing)
        self.assertFalse(self.gateway.running)
        self.assertEqual(self.runtime.status, "error")
        await self.runtime.configure(self.config)
        self.assertTrue(self.runtime.ready)

    async def test_event_poll_survives_database_failure_during_gateway_outage(self):
        async def finish_iteration(seconds):
            self.runtime.closing = True

        with patch.object(self.gateway, "call", side_effect=runtime_module.GatewayError("SIP unavailable")), \
             patch.object(self.runtime, "mark_offline", side_effect=RuntimeError("database unavailable")), \
             patch.object(self.runtime, "delay", side_effect=finish_iteration), \
             self.assertLogs(runtime_module.logger, level="ERROR"):
            await self.runtime._poll_loop()
        self.assertEqual(self.runtime.status, "error")
        self.assertFalse(self.runtime.ready)

    async def test_record_stop_waits_for_pending_start_and_keeps_preview(self):
        async with self.sessions() as db:
            device = await db.get(Device, 1)
            device.record_enabled = True
            await db.commit()
        started, finish = asyncio.Event(), asyncio.Event()
        original_start = self.media.start_record

        async def delayed_start(device_id):
            started.set()
            await finish.wait()
            return await original_start(device_id)

        with patch.object(self.media, "start_record", side_effect=delayed_start):
            preview = asyncio.create_task(self.runtime.acquire_lease(1, 1, None))
            await asyncio.wait_for(started.wait(), 2)
            stop = asyncio.create_task(self.runtime.set_recording(1, False))
            try:
                await asyncio.sleep(0.1)
                self.assertFalse(stop.done(), "stop must serialize with an in-flight recorder start")
            finally:
                finish.set()
                await asyncio.gather(preview, stop)
        self.assertFalse(await self.media.is_recording(1))
        self.assertTrue((await self.get(GbChannel, 1)).record_paused)
        self.assertIn(1, self.media.receivers)

    async def test_failed_manual_record_stop_is_retried_with_active_viewer(self):
        async with self.sessions() as db:
            device = await db.get(Device, 1)
            device.record_enabled = True
            await db.commit()
        await self.runtime.acquire_lease(1, 1, None)
        with patch.object(self.media, "stop_record", return_value=False):
            with self.assertRaises(GbError):
                await self.runtime.set_recording(1, False)
        self.assertTrue(await self.media.is_recording(1))
        await self.runtime.maintain()
        await self.wait_jobs()
        self.assertFalse(await self.media.is_recording(1))
        self.assertIn(1, self.media.receivers)

    async def test_expired_leases_are_collected_and_owner_cannot_renew_unknown_token(self):
        lease = await self.runtime.acquire_lease(1, 1, None)
        self.runtime.leases[1][lease["lease_id"]] = (1, time.monotonic() - 1)
        with self.assertRaises(GbError) as caught:
            await self.runtime.acquire_lease(1, 1, lease["lease_id"])
        self.assertEqual(caught.exception.status_code, 404)
        await self.runtime.maintain()
        await self.wait_jobs()
        self.assertFalse(self.media.receivers)


if __name__ == "__main__":
    unittest.main()
