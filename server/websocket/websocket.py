import socketio
from fastapi import FastAPI


def create_websocket(app: FastAPI, cors_allowed_origins: list | str):
    sio = socketio.AsyncServer(
        cors_allowed_origins=cors_allowed_origins,
        async_mode="asgi",
        # logger=True, engineio_logger=True
    )
    return sio, socketio.ASGIApp(sio, app)
