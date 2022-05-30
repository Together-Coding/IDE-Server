import json
import time

import socketio
from fastapi import FastAPI

from configs import settings
from constants.ws import WS_MONITOR_EVENTS, Room, WSEvent
from server.helpers.redis_ import r
from server.utils.etc import get_hostname

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
            d = r.get(f"monitor:{uuid}")
            if d:
                data.update(json.loads(d))

        return await super().emit(event, data, to, room, skip_sid, namespace, callback, **kwargs)

    async def _emit_internal(self, sid, event, data, namespace=None, id=None):
        if type(data) == dict and event not in WS_MONITOR_EVENTS:
            data["_ts_3"] = self._timestamp
            data["_ts_3_eid"] = sid  # event to. (sid == eio_sid) in this method
            data["_s_emit"] = event

        return await super()._emit_internal(sid, event, data, namespace, id)

    async def _handle_event(self, eio_sid, namespace, id, data):
        try:
            # if event != TIMESTAMP_ACK, then inject data
            if data[0] not in WS_MONITOR_EVENTS and type(data[1]) == dict and "uuid" in data[1]:
                r.set(
                    f'monitor:{data[1]["uuid"]}',
                    json.dumps(
                        {
                            "_ts_1": data[1].get("_ts_1"),
                            "_ts_1_eid": eio_sid,  # event by
                            "_ts_2": self._timestamp,
                            "_c_emit": data[0],
                        }
                    ),
                    ex=60,
                )
                _data = data[1].copy()
                _data["server"] = "Server-" + get_hostname()
                await self.emit(WSEvent.WS_MONITOR_EVENT, data=_data, to=Room.WS_MONITOR, uuid=data[1]['uuid'])
        except:
            pass

        return await super()._handle_event(eio_sid, namespace, id, data)
