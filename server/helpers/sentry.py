import sentry_sdk
from fastapi import FastAPI
from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

from configs import settings


def init_sentry(app: FastAPI):
    if not settings.DEBUG and settings.SENTRY_DSN:
        sentry_sdk.init(dsn=settings.SENTRY_DSN)
        app.add_middleware(SentryAsgiMiddleware)
