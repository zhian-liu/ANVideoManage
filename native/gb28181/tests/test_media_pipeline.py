"""Opt-in integration against real FastAPI, reSIProcate, ZLM and synthetic H.264.

Set GB28181_RUN_MEDIA_TESTS=1 and run with the backend virtual environment.
Every process, port, database and recording directory is isolated from the app.
FFmpeg is used only to create a test source; production GB playback needs no encoder.
"""
import configparser
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET

from test_sip_service import BINARY, Camera, CHANNEL, DEVICE, PLATFORM, REALM, ROOT, free_port

PROJECT = ROOT.parents[1]
ENABLED = os.environ.get("GB28181_RUN_MEDIA_TESTS") == "1"
FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def eventually(check, timeout=12):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.1)
    raise AssertionError("Timed out waiting for the media pipeline")


class RtpSource:
    """Mock device sender, not a media server. Uses RFC4571 framing for TCP."""

    def __init__(self, offer, sample, tcp):
        self.tcp, self.sample = tcp, sample
        self.host = re.search(r"(?m)^c=IN IP4 ([^\s]+)", offer)[1]
        self.port = int(re.search(r"(?m)^m=video (\d+)", offer)[1])
        self.ssrc = int(re.search(r"(?m)^y=(\d+)", offer)[1])
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM if tcp else socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(3)
        self.local_port = self.sock.getsockname()[1]
        self.stopped = threading.Event()
        self.thread = None
        self.error = None

    def start(self):
        if self.thread is not None:
            return
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        try:
            if self.tcp:
                self.sock.connect((self.host, self.port))
            payloads = [self.sample[i:i + 1200] for i in range(0, len(self.sample), 1200)]
            interval = 60 / len(payloads)
            started = time.monotonic()
            for sequence, payload in enumerate(payloads):
                if self.stopped.wait(max(0, started + sequence * interval - time.monotonic())):
                    break
                timestamp = int(sequence * interval * 90000) & 0xFFFFFFFF
                packet = struct.pack("!BBHII", 0x80, 96, sequence & 0xFFFF, timestamp, self.ssrc) + payload
                if self.tcp:
                    self.sock.sendall(struct.pack("!H", len(packet)) + packet)
                else:
                    self.sock.sendto(packet, (self.host, self.port))
        except OSError as exc:
            if not self.stopped.is_set():
                self.error = str(exc)

    def close(self):
        self.stopped.set()
        if self.thread:
            self.thread.join(timeout=4)
        self.sock.close()


class MockNvr:
    def __init__(self, sip_port, sample, sip_tcp, media_tcp):
        self.camera = Camera(sip_port, tcp=sip_tcp)
        self.sample, self.media_tcp = sample, media_tcp
        self.stopped = threading.Event()
        self.sources = {}
        self.invites = 0
        self.byes = 0
        self.error = None
        self.thread = None

    def start(self):
        status = self.camera.register()[0]
        if "200" not in status:
            raise AssertionError(f"Registration failed: {status}")
        self.camera.sock.settimeout(0.2)
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        heartbeat_at = time.monotonic()
        try:
            while not self.stopped.is_set():
                if time.monotonic() >= heartbeat_at:
                    body = (f"<Notify><CmdType>Keepalive</CmdType><SN>1</SN><DeviceID>{DEVICE}</DeviceID>"
                            "<Status>OK</Status></Notify>").encode()
                    self.camera.send_request("MESSAGE", body)
                    heartbeat_at = time.monotonic() + 3
                try:
                    packet = self.camera.receive()
                except socket.timeout:
                    continue
                line, headers, body = packet
                if line.startswith("SIP/2.0"):
                    continue
                method = line.split(" ", 1)[0]
                if method == "MESSAGE":
                    self.camera.respond(packet)
                    root = ET.fromstring(body)
                    command, sn = root.findtext("CmdType"), root.findtext("SN")
                    if command == "Catalog":
                        detail = (f'<SumNum>1</SumNum><DeviceList Num="1"><Item><DeviceID>{CHANNEL}</DeviceID>'
                                  "<Name>模拟摄像机</Name><Manufacturer>IntegrationTest</Manufacturer>"
                                  "<Status>ON</Status></Item></DeviceList>")
                    elif command == "DeviceInfo":
                        detail = "<DeviceName>模拟 NVR</DeviceName><Manufacturer>IntegrationTest</Manufacturer><Model>PS-RTP</Model>"
                    else:
                        continue
                    response = (f'<?xml version="1.0" encoding="UTF-8"?><Response><CmdType>{command}</CmdType>'
                                f"<SN>{sn}</SN><DeviceID>{DEVICE}</DeviceID>{detail}</Response>").encode()
                    self.camera.send_request("MESSAGE", response)
                elif method == "INVITE":
                    call_id = headers["call-id"]
                    if call_id not in self.sources:
                        self.invites += 1
                        self.sources[call_id] = RtpSource(body.decode(), self.sample, self.media_tcp)
                    source = self.sources[call_id]
                    answer = body.decode().replace("a=recvonly", "a=sendonly").replace("a=setup:passive", "a=setup:active")
                    answer = re.sub(r"(?m)^m=video \d+", f"m=video {source.local_port}", answer)
                    self.camera.respond(packet, body=answer.encode())
                elif method == "ACK":
                    self.sources[headers["call-id"]].start()
                elif method == "BYE":
                    self.byes += 1
                    self.camera.respond(packet)
                    source = self.sources.get(headers["call-id"])
                    if source:
                        source.close()
                elif method == "CANCEL":
                    self.camera.respond(packet)
        except Exception as exc:
            if not self.stopped.is_set():
                self.error = repr(exc)

    def close(self):
        self.stopped.set()
        if self.thread:
            self.thread.join(timeout=4)
        for source in self.sources.values():
            source.close()
        self.camera.close()


@unittest.skipUnless(ENABLED, "Set GB28181_RUN_MEDIA_TESTS=1 for isolated real-media tests")
class MediaPipelineTests(unittest.TestCase):
    def setUp(self):
        self.zlm_binary = Path(os.environ.get("GB28181_TEST_ZLM", str(
            PROJECT / "backend/ZLMediaKit/release/windows/Debug/Release/MediaServer.exe")))
        bundled = list((ROOT / ".deps/test-tools/imageio_ffmpeg/binaries").glob("*.exe"))
        self.ffmpeg = os.environ.get("GB28181_TEST_FFMPEG") or shutil.which("ffmpeg") or (str(bundled[0]) if bundled else None)
        self.assertTrue(BINARY.is_file(), "Build the native SIP service first")
        self.assertTrue(self.zlm_binary.is_file(), "Set GB28181_TEST_ZLM to a ZLM binary with RTP proxy support")
        self.assertTrue(self.ffmpeg, "Set GB28181_TEST_FFMPEG to an FFmpeg executable")
        self.temp = Path(tempfile.mkdtemp(prefix="media-test-", dir=ROOT / "build")).resolve()
        self.assertTrue(self.temp.is_relative_to((ROOT / "build").resolve()))
        self.processes, self.logs = [], []
        self.camera = None
        self.token = None
        self.config = None
        self.completed = False
        self.addCleanup(self.cleanup)
        self.api_port, self.zlm_port, self.sip_port, self.internal_port, self.rtsp_port = [free_port() for _ in range(5)]
        self.api_base = f"http://127.0.0.1:{self.api_port}"
        self.zlm_base = f"http://127.0.0.1:{self.zlm_port}"
        self.secret = uuid.uuid4().hex
        sample = self.temp / "test-pattern.ps"
        subprocess.run([self.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", "testsrc=size=96x64:rate=10", "-t", "60",
                        "-pix_fmt", "yuv420p", "-c:v", "libx264", "-profile:v", "baseline",
                        "-g", "10", "-preset", "ultrafast", "-tune", "zerolatency",
                        "-an", "-f", "vob", str(sample)], check=True, timeout=30, creationflags=FLAGS)
        self.sample = sample.read_bytes()
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str
        config.read_dict({
            "api": {"secret": self.secret, "apiDebug": "0"},
            "general": {"listen_ip": "127.0.0.1", "mediaServerId": uuid.uuid4().hex},
            "http": {"port": str(self.zlm_port), "sslport": "0", "rootPath": (self.temp / "www").as_posix()},
            "rtsp": {"port": str(self.rtsp_port), "sslport": "0"},
            "rtmp": {"port": "0", "sslport": "0"},
            "rtc": {"port": "0", "tcpPort": "0"},
            "srt": {"port": "0"}, "shell": {"port": "0"}, "onvif": {"port": "0"},
            "rtp_proxy": {"port": "0", "port_range": "39000-39998", "ps_pt": "96", "timeoutSec": "30"},
            "protocol": {"enable_audio": "0", "enable_hls": "0", "enable_rtsp": "1", "enable_rtmp": "1",
                         "enable_ts": "1", "enable_fmp4": "0", "enable_mp4": "0", "mp4_max_second": "2",
                         "mp4_save_path": (self.temp / "recordings").as_posix()},
            "hook": {"enable": "1", "timeoutSec": "2",
                     "on_stream_changed": self.api_base + "/api/zlm/hook/on_stream_changed",
                     "on_record_mp4": self.api_base + "/api/zlm/hook/on_record_mp4",
                     "on_publish": "", "on_play": "", "on_server_started": "", "on_server_keepalive": "",
                     "on_stream_none_reader": "", "on_stream_not_found": "", "on_rtp_server_timeout": ""},
        })
        path = self.temp / "zlm.ini"
        with path.open("w", encoding="utf-8") as output:
            config.write(output)
        self.spawn("zlm", [str(self.zlm_binary), "-c", str(path)])
        eventually(lambda: self.reachable(self.zlm_base + "/index/api/getServerConfig?secret=" + self.secret))
        env = dict(os.environ, PYTHONPATH=str(PROJECT / "backend"),
                   DATABASE_URL=f"sqlite+aiosqlite:///{(self.temp / 'test.db').as_posix()}",
                   SECRET_KEY=uuid.uuid4().hex, ADMIN_USERNAME="integration", ADMIN_PASSWORD="integration-test-password",
                   ZLM_API_BASE=self.zlm_base, ZLM_API_SECRET=self.secret, ZLM_APP="gb_test",
                   ZLM_HTTP_PORT=str(self.zlm_port), ZLM_RTSP_PORT=str(self.rtsp_port),
                   GB28181_HTTP_PORT=str(self.internal_port), GB28181_BINARY=str(BINARY),
                   GB28181_RUNTIME_DIR=str(self.temp / "sip-runtime"), WEBHOOK_BASE=self.api_base,
                   RECORDING_PATH="", SNAPSHOT_PATH=str(self.temp / "snapshots"), SENTRY_DSN="")
        self.spawn("backend", [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                               "--port", str(self.api_port)], env)
        eventually(lambda: self.reachable(self.api_base + "/api/health"))
        self.token = self.api("POST", "/api/auth/login", {"username": "integration", "password": "integration-test-password"})["access_token"]

    def spawn(self, name, command, env=None):
        log = (self.temp / f"{name}.log").open("wb")
        self.logs.append(log)
        process = subprocess.Popen(command, cwd=self.temp, env=env, stdout=log, stderr=log, creationflags=FLAGS)
        self.processes.append(process)

    def reachable(self, url):
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                return response.status == 200
        except (OSError, urllib.error.URLError):
            for process in self.processes:
                if process.poll() is not None:
                    self.fail(f"Isolated process exited with {process.returncode}; logs: {self.temp}")
            return False

    def api(self, method, path, payload=None):
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(self.api_base + path, method=method, headers=headers,
                                         data=json.dumps(payload).encode() if payload is not None else None)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            self.fail(f"{method} {path}: {exc.code} {exc.read().decode(errors='replace')}")

    def zlm(self, method):
        with urllib.request.urlopen(self.zlm_base + f"/index/api/{method}?secret={self.secret}", timeout=3) as response:
            result = json.load(response)
        self.assertEqual(result["code"], 0)
        return result.get("data") or []

    def cleanup(self):
        if self.config and self.token:
            try:
                self.api("PUT", "/api/gb28181/config", dict(self.config, enabled=False))
            except Exception:
                pass
        if self.camera:
            self.camera.close()
        for process in reversed(self.processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        for log in self.logs:
            log.close()
        if self.completed:
            # The path was resolved and checked against this task's build directory.
            shutil.rmtree(self.temp)
        else:
            print(f"Media integration logs retained at {self.temp}")
            for filename in ("backend.log", "zlm.log", "sip-runtime/sip-service.log"):
                path = self.temp / filename
                if path.is_file():
                    tail = path.read_text(encoding="utf-8", errors="replace")[-3500:]
                    print(f"{filename}:\n{tail}".encode("ascii", errors="backslashreplace").decode())

    def run_pipeline(self, sip_tcp, media_transport):
        self.config = {"enabled": True, "sip_id": PLATFORM, "realm": REALM, "listen_ip": "127.0.0.1",
                       "advertise_ip": "127.0.0.1", "sip_port": self.sip_port, "media_ip": "127.0.0.1",
                       "media_transport": media_transport, "heartbeat_timeout": 60,
                       "invite_timeout": 5, "media_timeout": 12, "catalog_timeout": 10}
        self.assertTrue(self.api("PUT", "/api/gb28181/config", self.config)["service"]["ready"])
        self.api("POST", "/api/gb28181/devices", {"id": DEVICE, "name": "Isolated NVR", "password": "camera-password"})
        self.camera = MockNvr(self.sip_port, self.sample, sip_tcp, media_transport == "tcp-passive")
        self.camera.start()
        eventually(lambda: self.api("GET", "/api/gb28181/devices")[0]["catalog_state"] == "complete")
        channel = self.api("GET", f"/api/gb28181/devices/{DEVICE}/channels")[0]
        self.assertEqual(channel["name"], "模拟摄像机")
        self.assertTrue(channel["online"])
        device_id = channel["device_id"]
        stream = f"device_{device_id}"
        lease = self.api("POST", f"/api/streams/{device_id}/lease", {})
        self.assertTrue(lease["online"])
        receivers = [item for item in self.zlm("listRtpServer") if item["stream_id"] == stream]
        self.assertEqual(len(receivers), 1)
        self.assertEqual(receivers[0]["tcp_mode"], 1 if media_transport == "tcp-passive" else 0)
        self.assertEqual(self.camera.invites, 1)
        with urllib.request.urlopen(lease["ts_url"], timeout=5) as response:
            ts = response.read(188 * 10)
        self.assertEqual(len(ts), 1880)
        self.assertTrue(all(ts[index] == 0x47 for index in range(0, len(ts), 188)))
        with urllib.request.urlopen(lease["flv_url"], timeout=5) as response:
            self.assertEqual(response.read(3), b"FLV")
        self.api("PUT", f"/api/devices/{device_id}", {"record_enabled": True})
        self.assertTrue(self.api("GET", f"/api/streams/{device_id}/record/status")["recording"])
        recordings = eventually(lambda: self.api("GET", f"/api/recordings?device_id={device_id}"))
        self.assertGreater(recordings[0]["file_size"], 0)
        file_url = self.api_base + f"/api/recordings/{recordings[0]['id']}/file?token=" + urllib.parse.quote(self.token)
        with urllib.request.urlopen(file_url, timeout=5) as response:
            self.assertIn(b"ftyp", response.read(32))
        self.api("DELETE", f"/api/streams/{device_id}/lease/{lease['lease_id']}")
        self.assertTrue(any(item["stream_id"] == stream for item in self.zlm("listRtpServer")))
        self.api("POST", f"/api/streams/{device_id}/record/stop")
        eventually(lambda: self.camera.byes >= 1)
        eventually(lambda: not any(item["stream_id"] == stream for item in self.zlm("listRtpServer")))
        # A stopped recorder stays stopped when the same channel is previewed again.
        lease = self.api("POST", f"/api/streams/{device_id}/lease", {})
        self.assertTrue(lease["online"])
        self.assertFalse(lease["recording"])
        self.assertEqual(self.camera.invites, 2)
        self.api("DELETE", f"/api/streams/{device_id}/lease/{lease['lease_id']}")
        eventually(lambda: self.camera.byes >= 2)
        eventually(lambda: not any(item["stream_id"] == stream for item in self.zlm("listRtpServer")))
        self.assertEqual(self.api("GET", f"/api/devices/{device_id}")["status"], "online")
        self.assertIsNone(self.camera.error)
        print(json.dumps({"sip": "TCP" if sip_tcp else "UDP", "media": media_transport,
                          "catalog": "complete", "http_ts_bytes": len(ts), "mp4_bytes": recordings[0]["file_size"],
                          "invites": self.camera.invites, "byes": self.camera.byes, "receivers_after_stop": 0}))
        self.completed = True

    def test_udp_sip_and_udp_ps_media(self):
        self.run_pipeline(False, "udp")

    def test_tcp_sip_and_tcp_passive_ps_media(self):
        self.run_pipeline(True, "tcp-passive")


if __name__ == "__main__":
    unittest.main()
