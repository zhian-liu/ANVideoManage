"""应用配置，通过环境变量 / .env 覆盖。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "视频监控管理平台"

    # 认证
    secret_key: str = "change-me-to-a-random-secret"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # 数据库
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    # 默认管理员（首次启动时创建）
    admin_username: str = "admin"
    admin_password: str = "admin123"

    # ZLMediaKit
    zlm_api_base: str = "http://127.0.0.1:8080"
    zlm_api_secret: str = ""
    zlm_app: str = "live"
    zlm_http_port: int = 8080
    zlm_rtsp_port: int = 554
    zlm_rtmp_port: int = 1935

    # 本后端地址（供 ZLMediaKit WebHook 回调）
    webhook_base: str = "http://127.0.0.1:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
