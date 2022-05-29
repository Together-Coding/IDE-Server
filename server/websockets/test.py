from constants.ws import Room, WSEvent
from server import sio
from server.utils.etc import get_hostname
from server.websockets import session as ws_session
from server.websockets.decorators import admin_only


@sio.on(WSEvent.WS_MONITOR)
@admin_only
async def enter_ws_monitor(sid: str, data: dict | None = None):
    await ws_session.enter_room(sid=sid, room_type=Room.WS_MONITOR, new_room=Room.WS_MONITOR, limit=1)

    await sio.emit(WSEvent.WS_MONITOR, data={"message": "hello"}, room=Room.WS_MONITOR)


@sio.on(WSEvent.TIMESTAMP_ACK)
async def get_timestamp_ack(sid: str, data: dict):
    data["server"] = get_hostname()
    await sio.emit(WSEvent.WS_MONITOR_EVENT, data=data, room=Room.WS_MONITOR)
