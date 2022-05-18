import functools
from typing import Awaitable

from constants.ws import WSEvent
from server import sio
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


def in_lesson(f: Awaitable):
    """
    Users must initialize a lesson first by INIT_LESSON event.
    If uninitialized user requests the decorated event handler, do not execute
    the handler and respond with error reason.
    """

    async def decorated(sid: str, *args, **kwargs):
        course_id: int = await ws_session.get(sid, "course_id")
        lesson_id: int = await ws_session.get(sid, "lesson_id")

        if not course_id or not lesson_id:
            msg = "수업에 접속한 상태가 아닙니다. `INIT_LESSON` 이벤트를 전송해주세요."
            return await sio.emit(WSEvent.ERROR, ws_error_response(msg), to=sid)

        return await f(sid, *args, **kwargs)

    return decorated
