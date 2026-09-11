"""Own a single native reSIProcate process; HTTP is restricted to loopback."""
import asyncio
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

import httpx

from app.config import settings
from app.schemas.gb28181 import GbConfig


class GatewayError(RuntimeError):
    pass


def binary_path() -> Path:
    if settings.gb28181_binary:
        return Path(settings.gb28181_binary).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent / "gb28181" / "gb28181-sip.exe"
    root = Path(__file__).resolve().parents[3]
    name = "gb28181-sip.exe" if os.name == "nt" else "gb28181-sip"
    folder = root / "native" / "gb28181" / "build" / "bin"
    return folder / "Release" / name if os.name == "nt" else folder / name


class SipGateway:
    def __init__(self):
        self.process: asyncio.subprocess.Process | None = None
        self.client: httpx.AsyncClient | None = None
        self.instance = ""
        self.log_file = None

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.returncode is None and self.client is not None

    def preflight(self) -> None:
        if not binary_path().is_file():
            raise GatewayError("尚未构建国标 SIP 服务，请运行 native/gb28181/build.ps1")
        if not 1 <= settings.gb28181_http_port <= 65535:
            raise GatewayError("GB28181_HTTP_PORT 无效")

    async def start(self, config: GbConfig) -> None:
        self.preflight()
        await self.stop()
        runtime = Path(settings.gb28181_runtime_dir).resolve()
        runtime.mkdir(parents=True, exist_ok=True)
        path = runtime / "runtime.json"
        payload = config.model_dump()
        payload.update(http_port=settings.gb28181_http_port, parent_pid=os.getpid())
        path.write_text(json.dumps(payload), encoding="utf-8")
        token = secrets.token_hex(32)
        env = dict(os.environ, GB28181_INTERNAL_TOKEN=token)
        self.log_file = (runtime / "sip-service.log").open("ab")
        try:
            self.process = await asyncio.create_subprocess_exec(
                str(binary_path()), "--config", str(path), env=env,
                stdout=self.log_file, stderr=self.log_file,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            self.client = httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{settings.gb28181_http_port}", timeout=8,
                headers={"Authorization": f"Bearer {token}"}, trust_env=False,
            )
            for _ in range(40):
                if self.process.returncode is not None:
                    raise GatewayError("国标 SIP 服务启动失败，请检查端口占用和 sip-service.log")
                try:
                    health = await self.call("GET", "/health")
                    self.instance = health["instance"]
                    return
                except GatewayError:
                    await asyncio.sleep(0.15)
            raise GatewayError("国标 SIP 服务启动超时")
        except BaseException:
            await self.stop()
            raise

    async def call(self, method: str, path: str, **kwargs):
        if not self.running or self.client is None:
            raise GatewayError("国标 SIP 服务未运行")
        try:
            response = await self.client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise GatewayError("无法连接国标 SIP 服务") from exc
        if response.status_code >= 400:
            # Native errors are bounded, constant messages, never echoed credentials.
            try:
                detail = response.json().get("error", "SIP command failed")
            except ValueError:
                detail = "SIP command failed"
            raise GatewayError(f"国标 SIP 请求失败：{detail}")
        return response.json()

    async def stop(self) -> None:
        process = self.process
        if process is not None and process.returncode is None:
            if self.client is not None:
                try:
                    await self.client.post("/v1/shutdown", timeout=2)
                except httpx.HTTPError:
                    pass
            try:
                await asyncio.wait_for(process.wait(), 3)
            except asyncio.TimeoutError:
                if process.returncode is None:
                    process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 3)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
        if self.client is not None:
            await self.client.aclose()
        if self.log_file is not None:
            self.log_file.close()
        self.process = self.client = self.log_file = None
        self.instance = ""
