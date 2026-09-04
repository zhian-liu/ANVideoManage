"""ZLMediaKit REST API 客户端与播放地址构造。"""
import httpx
from urllib.parse import urlsplit

from app.config import settings

DEFAULT_VHOST = "__defaultVhost__"


def stream_key(device_id: int) -> str:
    """设备对应的 ZLMediaKit stream 名，全局唯一。"""
    return f"device_{device_id}"


def _media_base() -> str:
    # ZLMediaKit 的 REST API 与媒体（HTTP-FLV/HLS）共用同一个 http 服务
    return settings.zlm_api_base.rstrip("/")


def flv_url(device_id: int) -> str:
    return f"{_media_base()}/{settings.zlm_app}/{stream_key(device_id)}.live.flv"


def ts_url(device_id: int) -> str:
    """返回 ZLMediaKit 的 HTTP MPEG-TS 地址（支持 H.264/H.265）。"""
    return f"{_media_base()}/{settings.zlm_app}/{stream_key(device_id)}.live.ts"


def hls_url(device_id: int) -> str:
    return f"{_media_base()}/{settings.zlm_app}/{stream_key(device_id)}/hls.m3u8"


def protocol_urls(device_id: int) -> list[dict[str, str]]:
    """返回设备流在 ZLMediaKit 上可使用的常见输出协议地址。"""
    parsed = urlsplit(_media_base())
    http_scheme = parsed.scheme if parsed.scheme in {"http", "https"} else "http"
    host = parsed.hostname or "127.0.0.1"
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    http_port = parsed.port or settings.zlm_http_port
    http_origin = f"{http_scheme}://{host}:{http_port}"
    ws_scheme = "wss" if http_scheme == "https" else "ws"
    ws_origin = f"{ws_scheme}://{host}:{http_port}"
    rtsp_origin = f"rtsp://{host}:{settings.zlm_rtsp_port}"
    rtmp_origin = f"rtmp://{host}:{settings.zlm_rtmp_port}"
    app = settings.zlm_app
    stream = stream_key(device_id)

    return [
        {
            "key": "rtsp",
            "name": "RTSP",
            "url": f"{rtsp_origin}/{app}/{stream}",
            "description": "适用于 VLC、PotPlayer、NVR 等播放器",
        },
        {
            "key": "rtmp",
            "name": "RTMP",
            "url": f"{rtmp_origin}/{app}/{stream}",
            "description": "适用于支持 RTMP 的播放器或推流工具",
        },
        {
            "key": "http-flv",
            "name": "HTTP-FLV",
            "url": f"{http_origin}/{app}/{stream}.live.flv",
            "description": "浏览器 FLV/MSE 播放地址",
        },
        {
            "key": "http-ts",
            "name": "HTTP-TS",
            "url": f"{http_origin}/{app}/{stream}.live.ts",
            "description": "MPEG-TS 播放地址，支持 H.264/H.265 封装",
        },
        {
            "key": "http-fmp4",
            "name": "HTTP-FMP4",
            "url": f"{http_origin}/{app}/{stream}.live.mp4",
            "description": "HTTP Fragmented MP4 播放地址",
        },
        {
            "key": "hls",
            "name": "HLS",
            "url": f"{http_origin}/{app}/{stream}/hls.m3u8",
            "description": "适用于 Safari、HLS.js 等播放器",
        },
        {
            "key": "ws-flv",
            "name": "WebSocket-FLV",
            "url": f"{ws_origin}/{app}/{stream}.live.flv",
            "description": "通过 WebSocket 传输的 FLV 流",
        },
        {
            "key": "ws-ts",
            "name": "WebSocket-TS",
            "url": f"{ws_origin}/{app}/{stream}.live.ts",
            "description": "通过 WebSocket 传输的 MPEG-TS 流",
        },
        {
            "key": "ws-fmp4",
            "name": "WebSocket-FMP4",
            "url": f"{ws_origin}/{app}/{stream}.live.mp4",
            "description": "通过 WebSocket 传输的 Fragmented MP4 流",
        },
        {
            "key": "webrtc",
            "name": "WebRTC",
            "url": f"{http_origin}/index/api/webrtc?app={app}&stream={stream}&type=play",
            "description": "WebRTC 播放信令地址，需使用 WebRTC 客户端完成协商",
        },
    ]


class ZLMClient:
    def __init__(self) -> None:
        self.base = settings.zlm_api_base.rstrip("/")
        self.secret = settings.zlm_api_secret

    def _url(self, path: str) -> str:
        url = f"{self.base}{path}"
        if self.secret:
            sep = "&" if "?" in path else "?"
            url += f"{sep}secret={self.secret}"
        return url

    async def add_stream_proxy(
        self, device_id: int, rtsp_url: str, enable_mp4: bool = True
    ) -> bool:
        body = {
            "vhost": DEFAULT_VHOST,
            "app": settings.zlm_app,
            "stream": stream_key(device_id),
            "url": rtsp_url,
            "enable_mp4": 1 if enable_mp4 else 0,
            "enable_rtsp": 1,
            "enable_rtmp": 1,
            "enable_hls": 1,
            "enable_ts": 1,
            "enable_fmp4": 1,
            # 浏览器端 MSE 播放链路通常不支持 PCMU/G.711；
            # 关闭转协议音频可避免实时播放失败，录像仍保留视频轨。
            "enable_audio": 0,
            "rtp_type": 0,
        }
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(self._url("/index/api/addStreamProxy"), json=body)
            return r.json().get("code") == 0

    async def del_stream_proxy(self, device_id: int) -> bool:
        key = f"{DEFAULT_VHOST}/{settings.zlm_app}/{stream_key(device_id)}"
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(self._url(f"/index/api/delStreamProxy?key={key}"))
            return r.json().get("code") == 0

    async def start_record(self, device_id: int) -> bool:
        params = {
            "type": 1,
            "vhost": DEFAULT_VHOST,
            "app": settings.zlm_app,
            "stream": stream_key(device_id),
        }
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(self._url("/index/api/startRecord"), params=params)
            data = r.json()
        return data.get("code") == 0 and bool(data.get("result", True))

    async def stop_record(self, device_id: int) -> bool:
        params = {
            "type": 1,
            "vhost": DEFAULT_VHOST,
            "app": settings.zlm_app,
            "stream": stream_key(device_id),
        }
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(self._url("/index/api/stopRecord"), params=params)
            data = r.json()
        return data.get("code") == 0 and bool(data.get("result", True))

    async def is_recording(self, device_id: int) -> bool:
        params = {
            "type": 1,
            "vhost": DEFAULT_VHOST,
            "app": settings.zlm_app,
            "stream": stream_key(device_id),
        }
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                r = await client.get(self._url("/index/api/isRecording"), params=params)
                data = r.json()
            except Exception:
                return False
        return data.get("code") == 0 and bool(data.get("status"))

    async def get_snapshot(self, source_url: str) -> bytes:
        params = {
            "url": source_url,
            "timeout_sec": 10,
            "expire_sec": 1,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(self._url("/index/api/getSnap"), params=params)
            r.raise_for_status()
        content_type = r.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            raise RuntimeError("ZLMediaKit 未返回图片")
        return r.content

    async def online_streams(self) -> set[str]:
        """返回当前在线流的 stream 名集合。"""
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                r = await client.get(self._url("/index/api/getMediaList"))
                data = r.json()
            except Exception:
                return set()
        if data.get("code") != 0:
            return set()
        return {
            s.get("stream")
            for s in data.get("data", [])
            if s.get("app") == settings.zlm_app
        }


zlm = ZLMClient()
