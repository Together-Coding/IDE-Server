from socketio.exceptions import ConnectionRefusedError

from constants.ws import WSEvent
from server import sio
from server.controllers.user import AuthController
from server.controllers.project import PingController
from server.helpers.db import get_db
from server.websockets import session as ws_session


@sio.event
async def connect(sid, environ, auth):
    token = ""
    for k, v in auth.items():
        k: str
        if k.lower() == "authorization":
            idx = v.lower().find("bearer")
            if idx != -1:
                token = v[idx + +len("bearer") :].strip()
            break

    if not token:
        raise ConnectionRefusedError("Authorization token is required.")

    token_info = AuthController.verify_token(token)

    # 에러 or 유효하지 않은 토큰
    if not token_info or type(token_info) == dict and token_info.get('valid', False) is False:
        raise ConnectionRefusedError("Authorization failed. Not a valid token.")

    # 유저 ID 저장
    await ws_session.update(sid, {'user_id': token_info['userId']})    


@sio.event
async def disconnect(sid):
    print("disconnect:", sid)


@sio.on("echo")
async def ws_echo(sid, data=None):
    await sio.emit("message", f"{data}", to=sid)
