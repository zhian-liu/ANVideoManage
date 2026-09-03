"""厂商私有 SDK 适配器模板（预留）。

示例：海康 SDK (HCNetSDK)、大华 SDK 等，功能最全（回放、PTZ、告警），
但需厂商提供的动态库/协议，按需逐个适配。

实现时新建子类继承 CameraAdapter，设置 access_type，实现 resolve_stream 与
PTZ 等能力，并在 registry 中注册。
"""
from app.adapters.base import CameraAdapter


class VendorSdkAdapter(CameraAdapter):
    access_type = "sdk"

    async def resolve_stream(self, device):
        raise NotImplementedError(
            "厂商私有 SDK 适配器尚未实现，请按具体厂商接入（如海康/大华）"
        )
