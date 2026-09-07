from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user
from app.database import get_db
from app.schemas.settings import DirectoryListOut, StorageSettingsOut, StorageSettingsUpdate
from app.services.storage import (
    browse_storage_directories,
    default_recording_path,
    default_snapshot_path,
    get_recording_retention_days,
    get_storage_values,
    set_storage_values,
)

router = APIRouter(
    prefix="/api/settings",
    tags=["settings"],
    dependencies=[Depends(get_current_user)],
)


def _response(
    recording_path: str, snapshot_path: str, recording_retention_days: int
) -> StorageSettingsOut:
    return StorageSettingsOut(
        recording_path=recording_path,
        snapshot_path=snapshot_path,
        recording_retention_days=recording_retention_days,
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
    retention_days = await get_recording_retention_days(db)
    return _response(recording_path, snapshot_path, retention_days)


@router.get("/directories", response_model=DirectoryListOut)
def browse_directories(path: str = Query("", max_length=512)):
    # A synchronous route keeps filesystem/drive access off the event loop.
    try:
        return browse_storage_directories(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="文件夹不存在，请选择其他路径")
    except NotADirectoryError:
        raise HTTPException(status_code=400, detail="请选择文件夹，不能选择文件")
    except PermissionError:
        raise HTTPException(status_code=403, detail="没有权限访问此文件夹")
    except (OSError, ValueError, RuntimeError):
        raise HTTPException(status_code=400, detail="无法访问此路径，请检查磁盘和文件夹")


@router.put("/storage", response_model=StorageSettingsOut)
async def update_storage(
    body: StorageSettingsUpdate, request: Request, db: AsyncSession = Depends(get_db)
):
    recording_path, snapshot_path = await set_storage_values(
        db,
        body.recording_path,
        body.snapshot_path,
        # Older clients only send paths; preserve their existing retention.
        recording_retention_days=(
            body.recording_retention_days
            if "recording_retention_days" in body.model_fields_set
            else None
        ),
    )
    retention_days = await get_recording_retention_days(db)
    wakeup = getattr(request.app.state, "recording_cleanup_wakeup", None)
    if wakeup is not None:
        wakeup.set()
    return _response(recording_path, snapshot_path, retention_days)
