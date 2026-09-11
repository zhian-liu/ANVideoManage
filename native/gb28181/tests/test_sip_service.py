"""Wire-level integration tests against the real, compiled reSIProcate service."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "build" / "bin" / "Release" / "gb28181-sip.exe"
if os.name != "nt":
    BINARY = ROOT / "build" / "bin" / "gb28181-sip"
DEVICE = "34020000001180000001"
CHANNEL = "34020000001320000001"
PLATFORM = "34020000002000000001"
REALM = "3402000000"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def parse_packet(packet):
    head, body = packet.split(b"\r\n\r\n", 1)
    lines = head.decode("utf-8").split("\r\n")
    headers = {}
    for line in lines[1:]:
        key, value = line.split(":", 1)
        headers[key.lower()] = value.strip()
    return lines[0], headers, body


class Camera:
    def __init__(self, port, tcp=False, device_id=DEVICE):
        self.port, self.tcp, self.id = port, tcp, device_id
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM if tcp else socket.SOCK_DGRAM)
        if tcp:
            self.sock.connect(("127.0.0.1", port))
        else:
            self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(4)
        self.local = self.sock.getsockname()[1]
        self.buffer = b""
        self.cseq = 0
        self.call = uuid.uuid4().hex

    def send(self, packet):
        if self.tcp:
            self.sock.sendall(packet)
        else:
            self.sock.sendto(packet, ("127.0.0.1", self.port))

    def receive(self):
        if not self.tcp:
            return parse_packet(self.sock.recv(262144))
        while True:
            if b"\r\n\r\n" in self.buffer:
                head, body = self.buffer.split(b"\r\n\r\n", 1)
                size = int(re.search(rb"(?i)Content-Length:\s*(\d+)", head)[1])
                if len(body) >= size:
                    packet = head + b"\r\n\r\n" + body[:size]
                    self.buffer = body[size:]
                    return parse_packet(packet)
            chunk = self.sock.recv(262144)
            if not chunk:
                raise ConnectionError("SIP connection closed")
            self.buffer += chunk

    def send_request(self, method, body=b"", extra=None):
        self.cseq += 1
        uri = f"sip:{PLATFORM}@{REALM}"
        headers = {
            "Via": f"SIP/2.0/{'TCP' if self.tcp else 'UDP'} 127.0.0.1:{self.local};rport;branch=z9hG4bK{uuid.uuid4().hex}",
            "From": f"<sip:{self.id}@{REALM}>;tag=camera",
            "To": f"<sip:{self.id}@{REALM}>",
            "Call-ID": self.call if method == "REGISTER" else uuid.uuid4().hex,
            "CSeq": f"{self.cseq} {method}",
            "Contact": f"<sip:{self.id}@127.0.0.1:{self.local}>",
            "Max-Forwards": "70",
            "Content-Length": str(len(body)),
        }
        if body:
            headers["Content-Type"] = "Application/MANSCDP+xml"
        headers.update(extra or {})
        packet = (f"{method} {uri} SIP/2.0\r\n" + "\r\n".join(f"{k}: {v}" for k, v in headers.items()) + "\r\n\r\n").encode() + body
        self.send(packet)

    def request(self, method, body=b"", extra=None):
        self.send_request(method, body, extra)
        return self.receive()

    def register(self, password="camera-password", expires=3600, qop=True):
        status, headers, _ = self.request("REGISTER", extra={"Expires": str(expires)})
        if "401" not in status:
            return status, headers, b""
        challenge = dict(re.findall(r'(\w+)="([^"]*)"', headers["www-authenticate"]))
        nonce, realm = challenge["nonce"], challenge["realm"]
        uri = f"sip:{PLATFORM}@{REALM}"
        md5 = lambda value: hashlib.md5(value.encode()).hexdigest()
        cnonce = uuid.uuid4().hex
        prefix = f'{md5(f"{self.id}:{realm}:{password}")}:{nonce}'
        response = md5(f'{prefix}:00000001:{cnonce}:auth:{md5(f"REGISTER:{uri}")}' if qop else f'{prefix}:{md5(f"REGISTER:{uri}")}')
        auth = f'Digest username="{self.id}", realm="{realm}", nonce="{nonce}", uri="{uri}", response="{response}", algorithm=MD5'
        if qop:
            auth += f', qop=auth, nc=00000001, cnonce="{cnonce}"'
        self.last_auth = auth
        return self.request("REGISTER", extra={"Expires": str(expires), "Authorization": auth})

    def respond(self, request, code=200, body=b""):
        _, h, _ = request
        headers = {"Via": h["via"], "From": h["from"], "To": h["to"] + ("" if ";tag=" in h["to"] else ";tag=answer"),
                   "Call-ID": h["call-id"], "CSeq": h["cseq"], "Contact": f"<sip:{CHANNEL}@127.0.0.1:{self.local}>",
                   "Content-Length": str(len(body))}
        if body:
            headers["Content-Type"] = "application/sdp"
        packet = (f"SIP/2.0 {code} Test\r\n" + "\r\n".join(f"{k}: {v}" for k, v in headers.items()) + "\r\n\r\n").encode() + body
        self.send(packet)

    def close(self):
        self.sock.close()


@unittest.skipUnless(BINARY.is_file(), "Build gb28181-sip first")
class SipServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="sip-test-", dir=ROOT / "build")
        self.temp = Path(self.directory.name).resolve()
        assert self.temp.is_relative_to((ROOT / "build").resolve())
        self.sip_port, self.http_port = free_port(), free_port()
        self.token = uuid.uuid4().hex + uuid.uuid4().hex
        config = {"sip_id": PLATFORM, "realm": REALM, "listen_ip": "127.0.0.1", "advertise_ip": "127.0.0.1",
                  "sip_port": self.sip_port, "http_port": self.http_port, "invite_timeout": 3}
        path = self.temp / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        self.log = (self.temp / "service.log").open("wb")
        self.proc = subprocess.Popen([str(BINARY), "--config", str(path)], stdout=self.log, stderr=self.log,
                                     env=dict(os.environ, GB28181_INTERNAL_TOKEN=self.token),
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.cameras = []
        for _ in range(60):
            try:
                self.api("GET", "/health")
                break
            except (OSError, urllib.error.URLError):
                if self.proc.poll() is not None:
                    self.fail((self.temp / "service.log").read_text(errors="replace"))
                time.sleep(0.05)
        else:
            self.fail("SIP service did not start")
        self.api("PUT", "/v1/devices", [{"id": DEVICE, "password": "camera-password", "enabled": True}])

    def tearDown(self):
        for camera in self.cameras:
            camera.close()
        try:
            self.api("POST", "/v1/shutdown")
            self.proc.wait(timeout=4)
        except Exception:
            self.proc.kill()
            self.proc.wait()
        self.log.close()
        if self._outcome.result.failures or self._outcome.result.errors:
            print((self.temp / "service.log").read_text(errors="replace")[-4000:])
        self.directory.cleanup()

    def api(self, method, path, payload=None):
        request = urllib.request.Request(f"http://127.0.0.1:{self.http_port}{path}", method=method,
                  data=json.dumps(payload).encode() if payload is not None else None,
                  headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.load(response)

    def camera(self, tcp=False, device_id=DEVICE):
        result = Camera(self.sip_port, tcp, device_id)
        self.cameras.append(result)
        return result

    def events(self):
        return self.api("GET", "/v1/events?after=0")["events"]

    def begin_invite(self, camera):
        session = uuid.uuid4().hex
        self.api("POST", "/v1/invite", {"session_id": session, "device_id": DEVICE, "channel_id": CHANNEL,
                   "ssrc": "0200000001", "sdp": "v=0\r\ns=Play\r\nm=video 30000 RTP/AVP 96\r\n"})
        invite = camera.receive()
        self.assertTrue(invite[0].startswith("INVITE "))
        return session, invite

    def test_udp_registration_digest_identity_and_heartbeat(self):
        camera = self.camera()
        self.assertIn("401", camera.register(password="wrong")[0])
        self.assertFalse(any(event["type"] == "registration" for event in self.events()))
        self.assertIn("200", camera.register()[0])
        body = f"<Notify><CmdType>Keepalive</CmdType><SN>1</SN><DeviceID>{DEVICE}</DeviceID><Status>OK</Status></Notify>".encode()
        self.assertIn("200", camera.request("MESSAGE", body)[0])
        messages = [event for event in self.events() if event["type"] == "message"]
        self.assertEqual(base64.b64decode(messages[-1]["body_base64"]), body)
        self.assertIn("403", self.camera(device_id=CHANNEL).register()[0])
        self.assertIn("200", camera.register(expires=0)[0])
        self.assertIn("403", camera.request("MESSAGE", body)[0])

    def test_tcp_registration_and_outgoing_xml_use_existing_connection(self):
        camera = self.camera(tcp=True)
        self.assertIn("200", camera.register()[0])
        xml = b"<Query><CmdType>Catalog</CmdType></Query>"
        self.api("POST", "/v1/message", {"device_id": DEVICE, "body_base64": base64.b64encode(xml).decode()})
        request = camera.receive()
        self.assertTrue(request[0].startswith("MESSAGE "))
        self.assertEqual(request[2], xml)
        camera.respond(request)
        self.assertEqual(self.events()[0]["transport"], "TCP")

    def test_digest_replay_cannot_move_registration_with_new_cseq_or_call_id(self):
        camera = self.camera()
        self.assertIn("200", camera.register()[0])
        self.assertIn("403", camera.request("REGISTER", extra={"Authorization": camera.last_auth})[0])
        other = self.camera()
        self.assertIn("401", other.request("REGISTER", extra={"Authorization": camera.last_auth})[0])
        registrations = [event for event in self.events() if event["type"] == "registration" and event.get("expires")]
        self.assertEqual(len(registrations), 1)
        self.assertEqual(registrations[0]["remote_port"], camera.local)

    def test_legacy_digest_can_renew_and_requires_fresh_challenge_on_source_change(self):
        camera = self.camera()
        self.assertIn("200", camera.register(qop=False)[0])
        self.assertIn("200", camera.request("REGISTER", extra={"Authorization": camera.last_auth})[0])
        other = self.camera()
        self.assertIn("401", other.request("REGISTER", extra={"Authorization": camera.last_auth})[0])
        self.assertIn("200", other.register(qop=False)[0])
        registrations = [event for event in self.events() if event["type"] == "registration" and event.get("expires")]
        self.assertEqual(registrations[-1]["remote_port"], other.local)

    def test_invite_repeated_success_ack_and_bye(self):
        camera = self.camera()
        self.assertIn("200", camera.register()[0])
        session, invite = self.begin_invite(camera)
        self.assertEqual(invite[1]["to"], f"<sip:{CHANNEL}@{REALM}>")
        camera.respond(invite, 200, b"v=0\r\nm=video 30000 RTP/AVP 96\r\n")
        ack = camera.receive()
        self.assertTrue(ack[0].startswith("ACK "))
        self.assertEqual(ack[1]["call-id"], invite[1]["call-id"])
        camera.respond(invite, 200, b"v=0\r\nm=video 30000 RTP/AVP 96\r\n")
        self.assertTrue(camera.receive()[0].startswith("ACK "))
        established = [e for e in self.events() if e.get("state") == "established"]
        self.assertEqual(len(established), 1)
        self.api("DELETE", f"/v1/sessions/{session}")
        bye = camera.receive()
        self.assertTrue(bye[0].startswith("BYE "))
        self.assertIn("tag=answer", bye[1]["to"])
        camera.respond(bye)
        self.api("DELETE", f"/v1/sessions/{session}")

    def test_cancel_then_late_success_gets_ack_and_bye(self):
        camera = self.camera()
        self.assertIn("200", camera.register()[0])
        session, invite = self.begin_invite(camera)
        camera.respond(invite, 100)
        time.sleep(0.05)
        self.api("DELETE", f"/v1/sessions/{session}")
        cancel = camera.receive()
        self.assertTrue(cancel[0].startswith("CANCEL "))
        self.assertEqual(cancel[1]["via"], invite[1]["via"])
        camera.respond(cancel)
        camera.respond(invite, 200, b"v=0\r\nm=video 30000 RTP/AVP 96\r\n")
        self.assertTrue(camera.receive()[0].startswith("ACK "))
        bye = camera.receive()
        self.assertTrue(bye[0].startswith("BYE "))
        camera.respond(bye)

    def test_registration_expiry_and_internal_auth(self):
        camera = self.camera()
        self.assertIn("200", camera.register(expires=1)[0])
        time.sleep(1.2)
        self.assertTrue(any(e.get("expires") == 0 for e in self.events()))
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(f"http://127.0.0.1:{self.http_port}/health", timeout=2)
        self.assertEqual(caught.exception.code, 401)


if __name__ == "__main__":
    unittest.main()
