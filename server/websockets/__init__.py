import socketio
from fastapi import FastAPI

from configs import settings

__all__ = [
    "main",
    "user",
    "project",
]


def create_websocket(app: FastAPI, cors_allowed_origins: list | str):
    message_queue = socketio.AsyncRedisManager(
        f"{settings.REDIS_URL}/{settings.REDIS_DB}", redis_options=dict(socket_timeout=10, socket_connect_timeout=10)
    )

    sio = socketio.AsyncServer(
        cors_allowed_origins=cors_allowed_origins,
        async_mode="asgi",
        client_manager=message_queue,
        logger=settings.DEBUG,
        engineio_logger=settings.DEBUG,
    )
    return sio, socketio.ASGIApp(sio, app)