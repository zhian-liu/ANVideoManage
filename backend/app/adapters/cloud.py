"""厂商云 API 适配器模板（预留）。

示例：小米米家、萤石云、TP-Link Kasa 等不暴露 RTSP 的智能摄像机。
实现时新建子类继承 CameraAdapter，设置 access_type 与厂商标识，
在 registry 中按 access_type 注册即可接入。

典型实现要点：
- resolve_stream：调用厂商开放平台换取临时拉流 URL（可能为 HLS/FLV），
  返回给 ZLMediaKit 拉流；若厂商仅提供 HLS，可直接返回 HLS 地址给前端。
- 云 API 通常需要 app_id / app_secret / access_token，建议扩展 Device 表字段。
"""
from app.adapters.base import CameraAdapter


class CloudApiAdapter(CameraAdapter):
    access_type = "cloud"

    async def resolve_stream(self, device):
        raise NotImplementedError(
            "厂商云 API 适配器尚未实现，请按具体厂商接入（如小米/萤石/TP-Link）"
        )
