"""GB/T28181 MANSCDP XML and the phase-one PS/RTP SDP profile."""
import re
import secrets
from dataclasses import dataclass
from xml.etree import ElementTree as ET

from app.schemas.gb28181 import GbConfig

MAX_XML_BYTES = 256 * 1024
MAX_CATALOG_ITEMS = 10000
VIDEO_DEVICE_TYPES = {"131", "132"}


def new_sn() -> int:
    return secrets.randbelow(2_147_483_646) + 1


def make_query(command: str, device_id: str, sn: int) -> bytes:
    if command not in {"Catalog", "DeviceInfo"} or not re.fullmatch(r"[0-9]{20}", device_id):
        raise ValueError("无效的国标查询")
    root = ET.Element("Query")
    ET.SubElement(root, "CmdType").text = command
    ET.SubElement(root, "SN").text = str(sn)
    ET.SubElement(root, "DeviceID").text = device_id
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


@dataclass(frozen=True)
class CatalogItem:
    id: str
    name: str
    manufacturer: str
    parent_id: str
    status: str

    @property
    def is_video(self) -> bool:
        return len(self.id) == 20 and self.id[10:13] in VIDEO_DEVICE_TYPES


@dataclass(frozen=True)
class GbMessage:
    command: str
    sn: int
    device_id: str
    root: ET.Element

    def text(self, name: str, max_length: int = 128) -> str:
        return (self.root.findtext(name) or "").strip()[:max_length]

    def catalog(self) -> tuple[int, list[CatalogItem]]:
        raw_total = self.root.findtext("SumNum") or ""
        if not raw_total.strip().isdigit():
            raise ValueError("Catalog 缺少有效的 SumNum")
        total = int(raw_total)
        if not 0 <= total <= MAX_CATALOG_ITEMS:
            raise ValueError("Catalog 总条目数超出限制")
        items: list[CatalogItem] = []
        listing = self.root.find("DeviceList")
        if listing is None and total != 0:
            raise ValueError("Catalog 缺少 DeviceList")
        if listing is not None:
            entries = listing.findall("Item")
            if "Num" in listing.attrib:
                try:
                    if int(listing.attrib["Num"]) != len(entries):
                        raise ValueError("Catalog Num 与本批条目数不一致")
                except (ValueError, TypeError):
                    raise ValueError("Catalog Num 与本批条目数不一致")
            for entry in entries:
                channel_id = (entry.findtext("DeviceID") or "").strip()
                if not re.fullmatch(r"[0-9]{2,20}", channel_id):
                    raise ValueError("Catalog 包含无效通道编码")
                status = (entry.findtext("Status") or "ON").strip().upper()
                items.append(CatalogItem(
                    id=channel_id,
                    name=(entry.findtext("Name") or channel_id).strip()[:128],
                    manufacturer=(entry.findtext("Manufacturer") or "").strip()[:128],
                    parent_id=(entry.findtext("ParentID") or "").strip()[:20],
                    status=status[:16],
                ))
        if len({item.id for item in items}) > total:
            raise ValueError("Catalog 条目数超过 SumNum")
        return total, items


def parse_message(raw: bytes, expected_device: str) -> GbMessage:
    if not raw or len(raw) > MAX_XML_BYTES or b"\x00" in raw:
        raise ValueError("国标 XML 为空、过大或编码不受支持")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("gb18030")
        except UnicodeDecodeError as exc:
            raise ValueError("国标 XML 编码错误") from exc
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", text, re.IGNORECASE):
        raise ValueError("国标 XML 不允许 DTD 或实体声明")
    # Expat does not support all multibyte encoding declarations. Decode first.
    text = re.sub(r"^\s*<\?xml[^?]*\?>", "", text, count=1)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise ValueError("国标 XML 格式错误") from exc
    nodes = list(root.iter())
    if len(nodes) > 100000:
        raise ValueError("国标 XML 节点过多")
    for node in nodes:
        node.tag = node.tag.rsplit("}", 1)[-1]
    command = (root.findtext("CmdType") or "").strip()
    expected_root = "Notify" if command == "Keepalive" else "Response"
    if command not in {"Keepalive", "Catalog", "DeviceInfo"} or root.tag != expected_root:
        raise ValueError("不支持的国标消息类型")
    device_id = (root.findtext("DeviceID") or "").strip()
    if device_id != expected_device:
        raise ValueError("XML 设备编码与已认证 SIP 设备不一致")
    try:
        sn = int(root.findtext("SN") or "")
    except ValueError as exc:
        raise ValueError("国标消息缺少有效 SN") from exc
    if not 0 < sn <= 2_147_483_647:
        raise ValueError("国标 SN 超出范围")
    return GbMessage(command, sn, device_id, root)


def allocate_ssrc(realm: str, used: set[int]) -> int:
    # GB live SSRC: 0 + domain digits 4..8 + four-digit sequence.
    for _ in range(10000):
        value = int(f"0{realm[3:8]}{secrets.randbelow(9999) + 1:04d}")
        if value not in used:
            return value
    raise RuntimeError("国标 SSRC 分配空间已满")


def make_live_sdp(config: GbConfig, channel_id: str, port: int, ssrc: int) -> str:
    if not re.fullmatch(r"[0-9]{20}", channel_id) or not 0 < port <= 65535:
        raise ValueError("无效的点播通道或 RTP 端口")
    protocol = "RTP/AVP" if config.media_transport == "udp" else "TCP/RTP/AVP"
    lines = [
        "v=0", f"o={config.sip_id} 0 0 IN IP4 {config.media_ip}", "s=Play",
        f"u={channel_id}:0", f"c=IN IP4 {config.media_ip}", "t=0 0",
        f"m=video {port} {protocol} 96", "a=recvonly", "a=rtpmap:96 PS/90000",
    ]
    if config.media_transport == "tcp-passive":
        lines += ["a=setup:passive", "a=connection:new"]
    lines += [f"y={ssrc:010d}"]
    return "\r\n".join(lines) + "\r\n"


def validate_answer(sdp: str, transport: str, ssrc: int) -> None:
    if len(sdp) > 64 * 1024:
        raise ValueError("设备 SDP 过大")
    lines = [line.strip() for line in sdp.splitlines()]
    media = next((line.split() for line in lines if line.startswith("m=video ")), [])
    protocol = "RTP/AVP" if transport == "udp" else "TCP/RTP/AVP"
    if len(media) < 4 or not media[1].isdigit() or not 0 < int(media[1]) <= 65535:
        raise ValueError("设备拒绝视频媒体或 SDP 缺少有效端口")
    if media[2].upper() != protocol or "96" not in media[3:]:
        raise ValueError("设备响应的媒体传输/负载与 PS/RTP 点播配置不一致")
    if not any(line.lower() == "a=rtpmap:96 ps/90000" for line in lines):
        raise ValueError("设备未接受 PS/90000 媒体格式")
    if "a=inactive" in lines or "a=recvonly" in lines:
        raise ValueError("设备未同意发送视频")
    if transport == "tcp-passive" and "a=setup:active" not in lines:
        raise ValueError("设备未接受主动 TCP 连接模式")
    answer_ssrc = next((line[2:] for line in lines if line.startswith("y=")), None)
    if answer_ssrc is not None and (not answer_ssrc.isdigit() or int(answer_ssrc) != ssrc):
        raise ValueError("设备响应的 SSRC 与接收端口不一致")
