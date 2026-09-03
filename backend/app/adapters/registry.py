"""适配器注册表：按设备 access_type 分发到对应适配器。"""
from app.adapters.base import CameraAdapter
from app.adapters.cloud import CloudApiAdapter
from app.adapters.onvif import OnvifAdapter
from app.adapters.sdk import VendorSdkAdapter

_REGISTRY: dict[str, CameraAdapter] = {
    "onvif": OnvifAdapter(),
    "cloud": CloudApiAdapter(),
    "sdk": VendorSdkAdapter(),
}


def get_adapter(access_type: str) -> CameraAdapter:
    return _REGISTRY.get(access_type, OnvifAdapter())


def register_adapter(adapter: CameraAdapter) -> None:
    """供后续新增厂商适配器时动态注册。"""
    _REGISTRY[adapter.access_type] = adapter
