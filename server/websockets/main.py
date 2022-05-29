import time
from typing import Any

from socketio.exceptions import ConnectionRefusedError

from configs import settings
from constants.ws import Room, WSEvent
from server import sio
from server.controllers.lesson import LessonUserController
from server.controllers.user import AuthController
from server.helpers.db import get_db
from server.websockets import session as ws_session


@sio.event
async def connect(sid: str, environ: dict, auth: dict[str, Any]):
    """웹소켓 연결 요청을 수신하였을 때, 토큰 인증을 실패한 경우에는 거절한다."""

    # Parse token from auth header
    token = ""
    for k, v in auth.items():
        if k.lower() == "authorization":
            idx = v.lower().find("bearer")
            if idx != -1:
                token = v[idx + len("bearer") :].strip()
            break
        elif k.lower() == "x-api-key":
            if v == settings.WS_MONITOR_KEY:
                # Bypass authorization and set connected
                return await ws_session.update(sid, {"admin": True})

    if not token:
        raise ConnectionRefusedError("Authorization token is required.")

    success, token_info = AuthController.verify_token(token)

    # 에러 or 유효하지 않은 토큰
    if not success:
        raise ConnectionRefusedError("Authorization failed. Not a valid token.")

    # 유저 ID 저장
    user_id = token_info["userId"]
    await ws_session.update(sid, {"user_id": user_id})


@sio.event
async def disconnect(sid: str):
    """Disconnected

    If the user initialized a lesson with `INIT_LESSON` and is in active status,
    toggle the flag and broadcast its change.
    """

    print("disconnect:", sid)
    try:
        # Change status and broadcast message
        ctrl = await LessonUserController.from_session(sid, get_db())
        await ctrl.update_ptc_status(active=False)
    except:
        pass


@sio.on("echo")
async def ws_echo(sid: str, data: Any = None):
    await sio.emit("message", f"{data}", to=sid)
