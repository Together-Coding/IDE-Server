from constants.ws import Room, WSEvent
from server import sio
from server.controllers.project import PingController
from server.helpers.db import get_db
from server.websockets import session as ws_session


@sio.on(WSEvent.ACTIVITY_PING)
async def ping(sid, data=None):
    user_id: int = await ws_session.get(sid, "user_id")
    course_id: int = await ws_session.get(sid, "course_id")
    lesson_id: int = await ws_session.get(sid, "lesson_id")

    ctrl = PingController(user_id=user_id, course_id=course_id, lesson_id=lesson_id, db=next(get_db()))
    ctrl.update_recent_activity()

    await sio.emit(WSEvent.ACTIVITY_PING, "pong", to=sid)
