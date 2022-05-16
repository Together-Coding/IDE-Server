import functools
from typing import Any, Awaitable

from socketio.exceptions import ConnectionRefusedError

from server import sio
from server.controllers.user import AuthController
from server.utils.response import ws_error_response
from server.websockets import session as ws_session



def requires(event: str, names: list):
    def decorator(f: Awaitable):
        @functools.wraps(f)
        async def decorated(sid: str, data: dict, *args, **kwargs):
            if type(data) != dict:
                data = {}

            errs = []
            for name in names:
                if name not in data:
                    errs.append(f"`{name}` is required.")
            if errs:
                return await sio.emit(event, ws_error_response(errs), to=sid)

            return await f(sid, data, *args, **kwargs)

        return decorated

    return decorator


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
    print("disconnect:", sid)


@sio.on("echo")
async def ws_echo(sid: str, data: Any = None):
    await sio.emit("message", f"{data}", to=sid)
