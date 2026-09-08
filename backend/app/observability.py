"""Application error reporting."""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.config import settings


def init_sentry() -> None:
    """Initialize Sentry when a DSN is configured; otherwise remain a no-op."""
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        send_default_pii=False,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=[FastApiIntegration(transaction_style="endpoint")],
    )


def capture_exception(error: BaseException) -> None:
    """Capture exceptions from handled background-task failures."""
    if settings.sentry_dsn:
        sentry_sdk.capture_exception(error)
