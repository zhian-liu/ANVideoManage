"""FastAPI 依赖注入：当前用户与角色鉴权。"""
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.database import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)


async def _user_from_token(raw: str, db: AsyncSession) -> User:
    try:
        payload = decode_token(raw)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效或已过期"
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效")
    user = await db.get(User, int(user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用"
        )
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _user_from_token(credentials.credentials, db)


async def get_current_user_flex(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    token: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """支持请求头或 query 参数两种携带令牌方式，供 <video>/<img> 等无法带头的场景使用。"""
    raw = credentials.credentials if credentials is not None else token
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _user_from_token(raw, db)


def require_roles(*roles: str):
    """角色鉴权依赖工厂，为多用户 RBAC 预留；MVP 仅 admin。"""

    async def _checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="权限不足"
            )
        return user

    return _checker
