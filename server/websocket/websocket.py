import socketio
from fastapi import FastAPI

from configs import settings


def create_websocket(app: FastAPI, cors_allowed_origins: list | str):
    message_queue = socketio.AsyncRedisManager(
        f"{settings.REDIS_URL}/{settings.REDIS_DB}", redis_options=dict(socket_timeout=10, socket_connect_timeout=10)
    )

    sio = socketio.AsyncServer(
        cors_allowed_origins=cors_allowed_origins,
        async_mode="asgi",
        client_manager=message_queue,
        # logger=True,
        # engineio_logger=True,
    )
    return sio, socketio.ASGIApp(sio, app)