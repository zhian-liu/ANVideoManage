"""GB business orchestration: SIP events, catalogs, media sessions and viewers."""
import asyncio
import base64
from contextlib import suppress
from datetime import datetime, timedelta
import logging
import time
import uuid

from fastapi import HTTPException
from sqlalchemy import select, update

from app.database import SessionLocal
from app.models import Device, GbChannel, GbDevice, GbStreamSession
from app.schemas.gb28181 import GbConfig
from app.services.gb_catalog import apply_catalog, channel_online, device_online, read_config
from app.services.gb_gateway import GatewayError, SipGateway
from app.services.gb_protocol import allocate_ssrc, make_live_sdp, make_query, new_sn, parse_message, validate_answer
from app.services.zlmediakit import flv_url, hls_url, stream_key, ts_url, zlm

logger = logging.getLogger(__name__)
LEASE_TTL = 45


class GbError(HTTPException):
    def __init__(self, detail: str, status_code: int = 502):
        super().__init__(status_code=status_code, detail=detail)


class GbRuntime:
    def __init__(self, sessions=SessionLocal, media=zlm, gateway=None):
        self.db = sessions
        self.media = media
        self.gateway = gateway if gateway is not None else SipGateway()
        self.config = GbConfig()
        self.status = "stopped"
        self.last_error = ""
        self.cursor = 0
        self.generation = 0
        self.control_lock = asyncio.Lock()
        self.locks: dict[int, asyncio.Lock] = {}
        self.catalog_locks: dict[str, asyncio.Lock] = {}
        self.waiters: dict[str, asyncio.Future] = {}
        self.leases: dict[int, dict[str, tuple[int, float]]] = {}
        self.jobs: dict[int, asyncio.Task] = {}
        self.next_attempt: dict[int, float] = {}
        self.loops: list[asyncio.Task] = []
        self.closing = False
        self.changing = False
        self.retry_at = 0.0
        self.wakeup = asyncio.Event()

    @property
    def ready(self) -> bool:
        return self.config.enabled and self.status == "running" and self.gateway.running and not self.changing

    def lock(self, device_id: int) -> asyncio.Lock:
        return self.locks.setdefault(device_id, asyncio.Lock())

    async def start(self, sessions=None):
        if sessions is not None:
            self.db = sessions
        self.closing = False
        self.wakeup = asyncio.Event()
        async with self.db() as db:
            config = await read_config(db)
        try:
            await self.configure(config)
        except GbError:
            logger.warning("GB service is unavailable; the rest of the application remains usable")
        self.loops = [
            asyncio.create_task(self._poll_loop(), name="gb-sip-events"),
            asyncio.create_task(self._maintenance_loop(), name="gb-media-maintenance"),
        ]

    async def close(self):
        self.closing = True
        self.wakeup.set()
        # Let in-flight SQLite work finish; cancelling aiosqlite connection creation
        # can leave the driver thread holding the database file open on Windows.
        await asyncio.gather(*self.loops, return_exceptions=True)
        self.loops.clear()
        with suppress(GbError):
            await self.configure(GbConfig())
        self.leases.clear()

    async def mark_offline(self):
        async with self.db() as db:
            await db.execute(update(GbDevice).values(registered_until=None))
            await db.execute(update(GbDevice).where(GbDevice.catalog_state == "syncing").values(
                catalog_state="error", last_error="信令服务已重启，请等待设备重新注册后同步目录",
            ))
            await db.commit()

    async def configure(self, config: GbConfig):
        async with self.control_lock:
            self.changing = True
            self.generation += 1
            self.config = config
            self.status = "starting" if config.enabled else "stopped"
            for waiter in self.waiters.values():
                if not waiter.done():
                    waiter.set_exception(GbError("国标服务配置已变化，请重新点播", 409))
            try:
                await asyncio.gather(*list(self.jobs.values()), return_exceptions=True)
                await self.mark_offline()
                async with self.db() as db:
                    ids = list(await db.scalars(select(GbStreamSession.device_id)))
                for device_id in ids:
                    try:
                        await self.stop_stream(device_id)
                    except GbError:
                        # Persisted allocation remains and the maintenance loop retries cleanup.
                        logger.warning("RTP cleanup pending for device %s", device_id)
                await self.gateway.stop()
                if config.enabled and not self.closing:
                    await self.gateway.start(config)
                    await self.sync_credentials()
                    self.cursor = 0
                    self.status = "running"
                self.last_error = ""
            except Exception as exc:
                await self.gateway.stop()
                self.status = "error"
                self.last_error = str(exc) if isinstance(exc, GatewayError) else "国标 SIP 服务启动失败"
                self.retry_at = time.monotonic() + 15
                raise GbError(self.last_error, 503) from exc
            finally:
                self.changing = False

    async def sync_credentials(self):
        if not self.gateway.running:
            return
        async with self.db() as db:
            devices = list(await db.scalars(select(GbDevice)))
        await self.gateway.call("PUT", "/v1/devices", json=[
            {"id": device.id, "password": device.password, "enabled": device.enabled}
            for device in devices
        ])

    async def query_catalog(self, device_id: str):
        if not self.ready:
            raise GbError("国标 SIP 服务未就绪", 503)
        async with self.catalog_locks.setdefault(device_id, asyncio.Lock()):
            sn = new_sn()
            async with self.db() as db:
                device = await db.get(GbDevice, device_id)
                if device is None:
                    raise GbError("国标设备不存在", 404)
                if not device_online(device, self.config):
                    raise GbError("国标设备尚未注册或心跳已超时", 409)
                if device.catalog_state == "syncing" and device.catalog_started_at and (
                    datetime.utcnow() - device.catalog_started_at).total_seconds() < self.config.catalog_timeout:
                    raise GbError("目录正在同步，请等待当前查询完成", 409)
                device.catalog_sn = sn
                device.catalog_expected = None
                device.catalog_received = 0
                device.catalog_state = "syncing"
                device.catalog_started_at = datetime.utcnow()
                device.last_error = ""
                await db.commit()
            try:
                await self.send_query(device_id, "Catalog", sn)
            except GatewayError as exc:
                await self.device_error(device_id, str(exc), catalog=True)
                raise GbError(str(exc)) from exc
        return sn

    async def send_query(self, device_id: str, command: str, sn: int):
        await self.gateway.call("POST", "/v1/message", json={
            "device_id": device_id, "body_base64": base64.b64encode(make_query(command, device_id, sn)).decode(),
        })

    async def device_error(self, device_id: str, detail: str, *, catalog: bool = False):
        async with self.db() as db:
            device = await db.get(GbDevice, device_id)
            if device is not None:
                device.last_error = detail[:512]
                if catalog:
                    device.catalog_state = "error"
                await db.commit()

    async def handle_event(self, event: dict):
        kind = event.get("type")
        if kind == "session":
            session_id = event["session_id"]
            future = self.waiters.get(session_id)
            if future is not None and not future.done():
                future.set_result(event)
            elif event.get("state") in {"ended", "failed"}:
                async with self.db() as db:
                    session = await db.scalar(select(GbStreamSession).where(GbStreamSession.session_id == session_id))
                    if session is not None:
                        session.state = "failed"
                        await db.commit()
            return
        device_id = event.get("device_id", "")
        registered = False
        async with self.db() as db:
            device = await db.get(GbDevice, device_id)
            if device is None or not device.enabled:
                return
            when = datetime.utcfromtimestamp(event["time"])
            if kind == "registration":
                expires = int(event.get("expires", 0))
                registered = expires > 0 and not device_online(device, self.config)
                device.registered_until = when + timedelta(seconds=expires) if expires else None
                if expires:
                    device.last_heartbeat = when  # Initial heartbeat grace period on REGISTER.
                    device.remote_ip = event.get("remote_ip", "")
                    device.remote_port = event.get("remote_port", 0)
                    device.transport = event.get("transport", "")
                    device.last_error = ""
                else:
                    device.last_error = "设备已注销、注册到期或连接已变化"
                await db.commit()
            elif kind == "message":
                if not device.registered_until or device.registered_until <= when:
                    return
                catalog_message = False
                try:
                    raw = base64.b64decode(event.get("body_base64", ""), validate=True)
                    message = parse_message(raw, device_id)
                    if message.command == "Keepalive":
                        if message.text("Status").upper() != "OK":
                            raise ValueError("设备心跳未报告 OK 状态")
                        device.last_heartbeat = when
                        await db.commit()
                    elif message.command == "DeviceInfo":
                        device.manufacturer = message.text("Manufacturer")
                        device.model = message.text("Model")
                        await db.commit()
                    elif message.command == "Catalog":
                        catalog_message = device.catalog_sn == message.sn
                        await apply_catalog(db, device, message)
                except ValueError as exc:
                    await db.rollback()
                    await self.device_error(device_id, str(exc), catalog=catalog_message)
        if registered:
            try:
                await self.send_query(device_id, "DeviceInfo", new_sn())
                await self.query_catalog(device_id)
            except (GatewayError, GbError) as exc:
                await self.device_error(device_id, exc.detail if isinstance(exc, GbError) else str(exc))

    async def _poll_loop(self):
        while not self.closing:
            try:
                if self.ready:
                    async with self.control_lock:
                        if not self.ready:
                            continue
                        batch = await self.gateway.call("GET", "/v1/events", params={"after": self.cursor})
                        if batch["instance"] != self.gateway.instance or batch.get("gap"):
                            raise GatewayError("国标事件队列已丢失，需要重新注册")
                        for event in batch["events"]:
                            await self.handle_event(event)
                            self.cursor = int(event["seq"])
                elif self.config.enabled and not self.changing and time.monotonic() >= self.retry_at:
                    await self.configure(self.config)
            except GatewayError as exc:
                self.last_error = str(exc)
                self.status = "error"
                self.retry_at = time.monotonic() + 5
                try:
                    await self.mark_offline()
                except Exception:
                    logger.exception("Could not mark GB devices offline; service recovery will retry")
            except GbError:
                pass
            except Exception:
                # Don't advance the event cursor on a DB failure; retry the same batch.
                logger.exception("Could not apply GB SIP events")
            await self.delay(0.5)

    async def binding(self, device_id: int):
        async with self.db() as db:
            device = await db.get(Device, device_id)
            channel = await db.scalar(select(GbChannel).where(GbChannel.device_id == device_id))
            parent = await db.get(GbDevice, channel.gb_device_id) if channel else None
        if device is None or channel is None or parent is None or device.access_type != "gb28181":
            raise GbError("国标通道不存在", 404)
        return device, channel, parent

    async def ensure_stream(self, device_id: int):
        async with self.lock(device_id):
            if not self.ready:
                raise GbError(self.last_error or "国标 SIP 服务未启动", 503)
            generation = self.generation
            device, channel, parent = await self.binding(device_id)
            if generation != self.generation or not self.ready:
                raise GbError("国标配置已变化，请重新点播", 409)
            if not device.enabled or not channel_online(channel, parent, self.config):
                raise GbError("国标通道未启用、设备离线或通道不在当前目录中", 409)
            async with self.db() as db:
                previous = await db.get(GbStreamSession, device_id)
            if previous and previous.state == "streaming" and stream_key(device_id) in await self.media.online_streams():
                await self.sync_recorder(device, channel)
                return
            if previous:
                await self._stop_locked(device_id)
            session_id = uuid.uuid4().hex
            future = asyncio.get_running_loop().create_future()
            self.waiters[session_id] = future
            try:
                async with self.db() as db:
                    ssrc = allocate_ssrc(self.config.realm, set(await db.scalars(select(GbStreamSession.ssrc))))
                    db.add(GbStreamSession(device_id=device_id, session_id=session_id, ssrc=ssrc))
                    # Persist intent before opening a port, so a crash can be cleaned up.
                    await db.commit()
                port = await self.media.open_rtp_server(device_id, ssrc, self.config.media_transport == "tcp-passive")
                async with self.db() as db:
                    session = await db.get(GbStreamSession, device_id)
                    session.rtp_port, session.state = port, "inviting"
                    await db.commit()
                if generation != self.generation:
                    raise GbError("国标配置已变化，请重新点播", 409)
                await self.gateway.call("POST", "/v1/invite", json={
                    "session_id": session_id, "device_id": parent.id, "channel_id": channel.channel_id,
                    "ssrc": f"{ssrc:010d}", "sdp": make_live_sdp(self.config, channel.channel_id, port, ssrc),
                })
                try:
                    answer = await asyncio.wait_for(future, self.config.invite_timeout + 2)
                except asyncio.TimeoutError as exc:
                    raise GbError("国标 INVITE 响应超时") from exc
                if answer.get("state") != "established":
                    raise GbError(f"设备拒绝或结束点播：{answer.get('reason', 'SIP session failed')}")
                validate_answer(answer.get("sdp", ""), self.config.media_transport, ssrc)
                deadline = time.monotonic() + self.config.media_timeout
                while stream_key(device_id) not in await self.media.online_streams():
                    if generation != self.generation:
                        raise GbError("国标配置已变化，请重新点播", 409)
                    if time.monotonic() >= deadline:
                        raise GbError("SIP 点播已建立，但未收到可播放媒体，请检查 RTP 地址、端口和设备编码")
                    await asyncio.sleep(0.25)
                # Re-read switches after network waits, before enabling a recorder.
                device, channel, parent = await self.binding(device_id)
                if generation != self.generation or not device.enabled or not channel_online(channel, parent, self.config):
                    raise GbError("通道状态已变化，点播已取消", 409)
                await self.sync_recorder(device, channel)
                async with self.db() as db:
                    session = await db.get(GbStreamSession, device_id)
                    session.state = "streaming"
                    await db.commit()
            except BaseException as exc:
                with suppress(GbError):
                    await asyncio.shield(self._stop_locked(device_id))
                if isinstance(exc, asyncio.CancelledError):
                    raise
                detail = exc.detail if isinstance(exc, GbError) else str(exc) if isinstance(exc, (GatewayError, ValueError, RuntimeError)) else "国标点播失败，请检查流媒体服务"
                await self.device_error(parent.id, detail)
                if isinstance(exc, GbError):
                    raise
                raise GbError(detail) from exc
            finally:
                self.waiters.pop(session_id, None)
                if future.done() and not future.cancelled():
                    future.exception()  # Observe a configuration-cancellation exception if not awaited.

    async def _stop_locked(self, device_id: int):
        async with self.db() as db:
            session = await db.get(GbStreamSession, device_id)
        if session is None:
            return
        if self.gateway.running:
            try:
                await self.gateway.call("DELETE", f"/v1/sessions/{session.session_id}")
            except GatewayError:
                # The media receiver still must be released if SIP became unavailable.
                logger.warning("SIP termination unavailable for device %s", device_id)
        try:
            await self.media.close_rtp_server(device_id)
        except Exception as exc:
            async with self.db() as db:
                current = await db.get(GbStreamSession, device_id)
                if current:
                    current.state = "cleanup"
                    await db.commit()
            raise GbError("RTP 接收资源尚未释放，将在流媒体服务恢复后重试") from exc
        async with self.db() as db:
            current = await db.get(GbStreamSession, device_id)
            if current and current.session_id == session.session_id:
                await db.delete(current)
                await db.commit()

    async def stop_stream(self, device_id: int):
        async with self.lock(device_id):
            await self._stop_locked(device_id)

    def viewers(self, device_id: int) -> bool:
        leases = self.leases.get(device_id, {})
        now = time.monotonic()
        for lease_id, (_, expires) in list(leases.items()):
            if expires <= now:
                leases.pop(lease_id, None)
        if not leases:
            self.leases.pop(device_id, None)
        return bool(leases)

    async def acquire_lease(self, device_id: int, owner: int, lease_id: str | None):
        self.viewers(device_id)
        leases = self.leases.setdefault(device_id, {})
        if lease_id is not None:
            previous = leases.get(lease_id)
            if previous is None:
                raise GbError("播放租约已过期，请重新打开画面", 404)
            if previous[0] != owner:
                raise GbError("无权续约此播放会话", 403)
        else:
            if sum(len(items) for items in self.leases.values()) >= 4096:
                raise GbError("播放租约数量已达上限", 429)
            lease_id = uuid.uuid4().hex
        # Reserve the viewer while SIP/media negotiation is pending. The advertised
        # lease lifetime starts when the response is ready, not when INVITE starts.
        setup_ttl = self.config.invite_timeout + self.config.media_timeout + LEASE_TTL
        leases[lease_id] = (owner, time.monotonic() + setup_ttl)
        try:
            await self.ensure_stream(device_id)
            info = await self.stream_info(device_id)
            self.leases.setdefault(device_id, {})[lease_id] = (owner, time.monotonic() + LEASE_TTL)
            return {**info, "lease_id": lease_id, "expires_in": LEASE_TTL}
        except BaseException:
            self.leases.get(device_id, {}).pop(lease_id, None)
            raise

    async def release_lease(self, device_id: int, owner: int, lease_id: str):
        leases = self.leases.get(device_id, {})
        previous = leases.get(lease_id)
        if previous and previous[0] != owner:
            raise GbError("无权释放此播放会话", 403)
        leases.pop(lease_id, None)
        await self.stop_if_unused(device_id)

    async def stop_if_unused(self, device_id: int):
        async with self.lock(device_id):
            await self._stop_if_unused_locked(device_id)

    async def _stop_if_unused_locked(self, device_id: int):
        device, channel, parent = await self.binding(device_id)
        allowed = self.ready and device.enabled and channel_online(channel, parent, self.config)
        if allowed and (self.viewers(device_id) or (device.record_enabled and not channel.record_paused)):
            return
        await self._stop_locked(device_id)

    async def stream_info(self, device_id: int) -> dict:
        online = stream_key(device_id) in await self.media.online_streams()
        return {"device_id": device_id, "online": online,
                "recording": await self.media.is_recording(device_id) if online else False,
                "ts_url": ts_url(device_id), "flv_url": flv_url(device_id), "hls_url": hls_url(device_id)}

    async def sync_recorder(self, device: Device, channel: GbChannel):
        # Caller holds the channel lock, including across start/stop network waits.
        recording = await self.media.is_recording(device.id)
        desired = device.enabled and device.record_enabled and not channel.record_paused
        if desired and not recording:
            if not await self.media.start_record(device.id):
                raise GbError("国标流已上线，但启动本地录像失败")
        elif not desired and recording:
            if not await self.media.stop_record(device.id):
                raise GbError("停止国标通道录像失败")

    async def apply_device(self, device: Device):
        async with self.lock(device.id):
            device, channel, _ = await self.binding(device.id)
            if not device.enabled:
                self.leases.pop(device.id, None)
                await self._stop_locked(device.id)
                return
            if not device.record_enabled or channel.record_paused:
                await self.sync_recorder(device, channel)
                await self._stop_if_unused_locked(device.id)
                return
        await self.ensure_stream(device.id)

    async def set_recording(self, device_id: int, recording: bool):
        async with self.lock(device_id):
            device, channel, _ = await self.binding(device_id)
            if recording and (not device.enabled or not device.record_enabled):
                raise GbError("请先启用设备及录像开关", 403)
            async with self.db() as db:
                current = await db.get(GbChannel, channel.id)
                current.record_paused = not recording
                await db.commit()
            if not recording:
                channel.record_paused = True
                await self.sync_recorder(device, channel)
                await self._stop_if_unused_locked(device_id)
        if recording:
            await self.ensure_stream(device_id)

    def schedule(self, device_id: int, *, stop: bool = False):
        if device_id in self.jobs and not self.jobs[device_id].done():
            return
        async def perform():
            try:
                if stop:
                    try:
                        await self.stop_if_unused(device_id)
                    except GbError as exc:
                        if exc.status_code != 404:
                            raise
                        await self.stop_stream(device_id)
                else:
                    await self.ensure_stream(device_id)
            except GbError as exc:
                logger.warning("GB device %s: %s", device_id, exc.detail)
            finally:
                self.next_attempt[device_id] = time.monotonic() + 5
        task = asyncio.create_task(perform(), name=f"gb-device-{device_id}")
        self.jobs[device_id] = task
        def complete(done):
            if self.jobs.get(device_id) is done:
                self.jobs.pop(device_id, None)
            if not done.cancelled() and done.exception():
                logger.error("GB device task failed for %s: %s", device_id, type(done.exception()).__name__)
        task.add_done_callback(complete)

    async def maintain(self):
        if self.changing:
            return
        async with self.db() as db:
            rows = list(await db.execute(select(Device, GbChannel, GbDevice)
                .join(GbChannel, GbChannel.device_id == Device.id)
                .join(GbDevice, GbDevice.id == GbChannel.gb_device_id)))
            sessions = {item.device_id: item for item in await db.scalars(select(GbStreamSession))}
            stale = datetime.utcnow() - timedelta(seconds=self.config.catalog_timeout)
            await db.execute(update(GbDevice).where(
                GbDevice.catalog_state == "syncing", GbDevice.catalog_started_at < stale,
            ).values(catalog_state="error", last_error="目录同步超时，旧通道已保留，请重新同步"))
            await db.commit()
        online = await self.media.online_streams() if sessions else set()
        handled = set()
        for device, channel, parent in rows:
            handled.add(device.id)
            watching = self.viewers(device.id)
            recording = device.record_enabled and not channel.record_paused
            desired = self.ready and device.enabled and channel_online(channel, parent, self.config) and (watching or recording)
            if self.lock(device.id).locked() or time.monotonic() < self.next_attempt.get(device.id, 0):
                continue
            if desired:
                session = sessions.get(device.id)
                if not session or session.state != "streaming" or stream_key(device.id) not in online or recording or channel.record_paused:
                    self.schedule(device.id)
            elif device.id in sessions:
                self.schedule(device.id, stop=True)
        for device_id in sessions.keys() - handled:
            self.schedule(device_id, stop=True)

    async def _maintenance_loop(self):
        while not self.closing:
            try:
                await self.maintain()
            except Exception:
                logger.exception("GB media maintenance will retry")
            await self.delay(2)

    async def delay(self, seconds: float):
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self.wakeup.wait(), seconds)


gb_runtime = GbRuntime()
