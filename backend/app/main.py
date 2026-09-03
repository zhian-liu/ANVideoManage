from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from starlette.exceptions import HTTPException

from app.api import auth, devices, ptz, recordings, streams, zlm_hook
from app.config import settings
from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import User


class SPAStaticFiles(StaticFiles):
    """Serve the React entry point for client-side routes in packaged builds."""

    def __init__(self, directory: str | Path):
        super().__init__(directory=directory, html=True)
        self.index_path = Path(directory) / "index.html"

    async def get_response(self, path: str, scope):
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or path.startswith("api/"):
                raise
            return FileResponse(self.index_path)

        if response.status_code == 404 and not path.startswith("api/"):
            return FileResponse(self.index_path)
        return response


def _ensure_sqlite_dir() -> None:
    if settings.database_url.startswith("sqlite"):
        path = settings.database_url.split("///", 1)[-1]
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_sqlite_dir()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # 种子默认管理员
    async with SessionLocal() as session:
        result = await session.execute(
            select(User).where(User.username == settings.admin_username)
        )
        if result.scalar_one_or_none() is None:
            session.add(
                User(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                    role="admin",
                )
            )
            await session.commit()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(streams.router)
app.include_router(recordings.router)
app.include_router(ptz.router)
app.include_router(zlm_hook.router)


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
@app.get("/api/health")
async def health():
    return {"status": "ok"}


if (frontend_dist / "index.html").is_file():
    app.mount("/", SPAStaticFiles(frontend_dist), name="frontend")
