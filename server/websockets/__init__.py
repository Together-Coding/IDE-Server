import json
import time

import socketio
from fastapi import FastAPI

from configs import settings
from constants.ws import WS_MONITOR_EVENTS, Room, WSEvent
from server.helpers.redis_ import r
from server.utils.etc import get_server_ident

__all__ = [
    "main",
    "project",
    "lesson",
    "cursor",
    "code",
    "feedback",
    "test",
]


def create_websocket(app: FastAPI, cors_allowed_origins: list | str):
    message_queue = socketio.AsyncRedisManager(
        f"{settings.REDIS_URL}/{settings.REDIS_DB}", redis_options=dict(socket_timeout=10, socket_connect_timeout=10)
    )

    kwargs = dict(
        cors_allowed_origins=cors_allowed_origins,
        async_mode="asgi",
        client_manager=message_queue,
        logger=settings.WS_DEBUG,
        engineio_logger=settings.WS_DEBUG,
    )

    sio = CompatibleAsyncServer(**kwargs) if not settings.WS_MONITOR else AsyncServerForMonitor(**kwargs)
    return sio, socketio.ASGIApp(sio, app)


class CompatibleAsyncServer(socketio.AsyncServer):
    """For compatibility with AsyncServerForMonitor"""

    async def emit(
        self, event, data=None, to=None, room=None, skip_sid=None, namespace=None, callback=None, uuid=None, **kwargs
    ):
        """Remove ``uuid`` from kwargs"""
        return await super().emit(event, data, to, room, skip_sid, namespace, callback, **kwargs)


message_box = {}


class AsyncServerForMonitor(socketio.AsyncServer):
    @property
    def _timestamp(self):
        return int(time.time() * 1000)

    async def emit(
        self, event, data=None, to=None, room=None, skip_sid=None, namespace=None, callback=None, uuid=None, **kwargs
    ):
        """Inject data for debug

        Args:
            uuid (str | None): UUID of invoking this emit
        """

        if uuid and type(data) == dict:
            data["uuid"] = uuid
            d = message_box.pop(uuid, None)
            if d:
                data.update(d)

        return await super().emit(event, data, to, room, skip_sid, namespace, callback, **kwargs)

    async def _emit_internal(self, sid, event, data, namespace=None, id=None):
        if type(data) == dict and event not in WS_MONITOR_EVENTS:
            data["_ts_3"] = self._timestamp
            data["_ts_3_eid"] = sid  # event to. (sid == eio_sid) in this method
            data["_s_emit"] = event

        return await super()._emit_internal(sid, event, data, namespace, id)

    async def _handle_event_internal(self, server, sid, eio_sid, data, namespace, id):
        from server.websockets import session as ws_session

        try:
            # if event != TIMESTAMP_ACK, then inject data
            if data[0] not in WS_MONITOR_EVENTS and type(data[1]) == dict and "uuid" in data[1]:
                message_box[data[1]["uuid"]] = {
                    "_ts_1": data[1].get("_ts_1"),
                    "_ts_1_eid": eio_sid,  # event by
                    "_ts_2": self._timestamp,
                    "_c_emit": data[0],
                }
                data[1]["server"] = get_server_ident()
                course_id = await ws_session.get(sid, "course_id")
                lesson_id = await ws_session.get(sid, "lesson_id")
                monitor_room = Room.WS_MONITOR.format(course_id=course_id, lesson_id=lesson_id)
                await self.emit(
                    WSEvent.WS_MONITOR_EVENT,
                    data=data[1],
                    room=monitor_room,
                    uuid=data[1]["uuid"],
                )
        except:
            pass

        return await super()._handle_event_internal(server, sid, eio_sid, data, namespace, id)
