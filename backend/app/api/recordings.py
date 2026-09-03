from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_current_user_flex
from app.database import get_db
from app.models import Recording
from app.schemas.recording import RecordingOut

router = APIRouter(prefix="/api/recordings", tags=["recordings"])


@router.get("", response_model=list[RecordingOut])
async def list_recordings(
    device_id: int | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    limit: int = Query(200, le=1000),
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    stmt = select(Recording).order_by(Recording.start_time.desc()).limit(limit)
    if device_id is not None:
        stmt = stmt.where(Recording.device_id == device_id)
    if start is not None:
        stmt = stmt.where(Recording.end_time >= start)
    if end is not None:
        stmt = stmt.where(Recording.start_time <= end)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{recording_id}/file")
async def recording_file(
    recording_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user_flex),
):
    rec = await db.get(Recording, recording_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="录像不存在")
    path = Path(rec.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="录像文件不存在")
    return FileResponse(path, media_type="video/mp4", filename=rec.file_name)


@router.delete("/{recording_id}", status_code=204)
async def delete_recording(
    recording_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    rec = await db.get(Recording, recording_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="录像不存在")
    try:
        Path(rec.file_path).unlink(missing_ok=True)
    except Exception:
        pass
    await db.delete(rec)
    await db.commit()
    return Response(status_code=204)
