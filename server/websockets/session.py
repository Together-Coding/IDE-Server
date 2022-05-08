from typing import Any

from server import sio


def is_connected(sid, namespaces: str = None):
    return sio.manager.is_connected(sid, namespaces)


async def get(sid: str, key: str, namespaces: str = None) -> Any:
    s = await sio.get_session(sid, namespaces)
    return s.get(key)


async def update(sid: str, data: dict, namespaces: str = None) -> dict:
    """Update sio session"""

    async with sio.session(sid, namespaces) as s:
        s.update(data)
        return s


async def clear(sid: str, exc: list[str] | None = None, namespaces: str = None) -> None:
    """Clear sio session except ``exc`` keys"""

    async with sio.session(sid, namespaces) as s:
        if not s:
            return

        for k in list(s.keys()):
            if exc and k in exc:
                continue
            else:
                del s[k]


async def enter_room(sid: str, room_type: str, new_room: str, limit=None):
    """``room_type``별 최대 limit 개의 room 에 접속한다."""

    # 기존에 접속한 room 을 가져온다.
    room_key = f"room-{room_type}"
    rooms: list = await get(sid, room_key) or []

    # If already enterred, do nothing.
    if new_room in rooms:
        return

    # ``limit`` 을 초과한 경우, 개수를 조정해준다.
    rooms_to_exit = []
    if limit and len(rooms) >= limit:
        rooms_to_exit.extend(rooms[-limit:])

    for room in rooms_to_exit:
        await exit_room(sid, room_type, room)

    # Enter new room
    sio.enter_room(sid, new_room)

    rooms.append(new_room)
    await update(sid, {room_key: rooms})


async def exit_room(sid: str, room_type: str, room: str):
    """room 을 떠나고, ``room_type``에서 해당 room 을 제거한다."""

    # 기존에 접속한 room 을 가져온다.
    room_key = f"room-{room_type}"
    rooms: list = await get(sid, room_key) or []

    # If not enterred, do nothing.
    if room not in rooms:
        return

    # Exit room
    sio.leave_room(sid, room)

    rooms.remove(room)
    await update(sid, {room_key: rooms})
