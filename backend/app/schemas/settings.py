from pydantic import BaseModel, Field, field_validator


def _validate_path(value: str) -> str:
    if "\x00" in value:
        raise ValueError("路径不能包含空字符")
    return value.strip()


class StorageSettingsUpdate(BaseModel):
    recording_path: str = Field("", max_length=512)
    snapshot_path: str = Field("", max_length=512)

    _path_validator = field_validator("recording_path", "snapshot_path")(_validate_path)


class StorageSettingsOut(BaseModel):
    recording_path: str
    snapshot_path: str
    recording_path_default: str
    snapshot_path_default: str
    backend_base: str
    zlm_api_base: str
    zlm_http_port: int
    zlm_rtsp_port: int
    zlm_rtmp_port: int


class SnapshotSaveOut(BaseModel):
    ok: bool = True
    file_name: str
    file_path: str
