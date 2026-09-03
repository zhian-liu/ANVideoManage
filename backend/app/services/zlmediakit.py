"""ZLMediaKit REST API 客户端与播放地址构造。"""
import httpx

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


def hls_url(device_id: int) -> str:
    return f"{_media_base()}/{settings.zlm_app}/{stream_key(device_id)}/hls.m3u8"


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
            "enable_fmp4": 1,
            # 浏览器端 flv.js 只支持 AAC/MP3；许多摄像机输出 PCMU/G.711，
            # 关闭转协议音频可避免 FLV 播放失败，录像仍保留视频轨。
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
