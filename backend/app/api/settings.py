from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user
from app.database import get_db
from app.schemas.settings import StorageSettingsOut, StorageSettingsUpdate
from app.services.storage import (
    default_recording_path,
    default_snapshot_path,
    get_storage_values,
    set_storage_values,
)

router = APIRouter(
    prefix="/api/settings",
    tags=["settings"],
    dependencies=[Depends(get_current_user)],
)


def _response(recording_path: str, snapshot_path: str) -> StorageSettingsOut:
    return StorageSettingsOut(
        recording_path=recording_path,
        snapshot_path=snapshot_path,
        recording_path_default=default_recording_path(),
        snapshot_path_default=default_snapshot_path(),
        backend_base=settings.webhook_base,
        zlm_api_base=settings.zlm_api_base,
        zlm_http_port=settings.zlm_http_port,
        zlm_rtsp_port=settings.zlm_rtsp_port,
        zlm_rtmp_port=settings.zlm_rtmp_port,
    )


@router.get("", response_model=StorageSettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    recording_path, snapshot_path = await get_storage_values(db)
    return _response(recording_path, snapshot_path)


@router.put("/storage", response_model=StorageSettingsOut)
async def update_storage(
    body: StorageSettingsUpdate, db: AsyncSession = Depends(get_db)
):
    recording_path, snapshot_path = await set_storage_values(
        db, body.recording_path, body.snapshot_path
    )
    return _response(recording_path, snapshot_path)
