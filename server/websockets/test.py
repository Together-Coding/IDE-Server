from constants.ws import Room, WSEvent
from server import sio
from server.utils.etc import get_server_ident
from server.websockets import session as ws_session
from server.websockets.decorators import admin_only


@sio.on(WSEvent.WS_MONITOR)
@admin_only
async def enter_ws_monitor(sid: str, data: dict | None = None):
    course_id = data.get("course_id")
    lesson_id = data.get("lesson_id")
    monitor_room = Room.WS_MONITOR.format(course_id=course_id, lesson_id=lesson_id)

    await ws_session.enter_room(sid=sid, room_type=WSEvent.WS_MONITOR, new_room=monitor_room, limit=1)

    await sio.emit(WSEvent.WS_MONITOR, data={"message": "hello"}, room=sid)


@sio.on(WSEvent.TIMESTAMP_ACK)
async def get_timestamp_ack(sid: str, data: dict):
    data["server"] = get_server_ident()
    data["time_diff"] = await ws_session.get(sid, "time_diff")

    course_id = await ws_session.get(sid, "course_id")
    lesson_id = await ws_session.get(sid, "lesson_id")
    monitor_room = Room.WS_MONITOR.format(course_id=course_id, lesson_id=lesson_id)
    await sio.emit(WSEvent.WS_MONITOR_EVENT, data=data, room=monitor_room)
