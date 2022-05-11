import traceback

import sentry_sdk
from fastapi import FastAPI
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

from configs import settings


def init_sentry(app: FastAPI):
    if not settings.DEBUG and settings.SENTRY_DSN:
        sentry_sdk.init(dsn=settings.SENTRY_DSN)
        app.add_middleware(SentryAsgiMiddleware)


def exc(*args, **kwargs) -> str | None:
    if settings.DEBUG:
        traceback.print_exc()

    return sentry_sdk.capture_exception(*args, **kwargs)


def msg(*args, **kwargs) -> str | None:
    if settings.DEBUG:
        traceback.print_exc()

    return sentry_sdk.capture_message(*args, **kwargs)
