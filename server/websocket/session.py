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
