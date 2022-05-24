from constants.ws import Room, WSEvent
from server import sio
from server.controllers.project import ProjectFileController
from server.helpers import sentry
from server.helpers.db import get_db
from server.models.course import PROJ_PERM
from server.utils.exceptions import BaseException
from server.utils.response import ws_error_response
from server.websockets import session as ws_session
from server.websockets.decorators import in_lesson, requires


@sio.on(WSEvent.FILE_MOD)
@requires(WSEvent.FILE_MOD, ["ownerId", "file", "cursor", "change", "timestamp"])
@in_lesson
async def broadcast_file_mod(sid: str, data: dict):
    """Broadcast file modification.

    data: {
        ownerId (int): file owner's participant ID
        file (str): filename
        cursor (str): cursor info
        change (list[int | str]): enterred characters
        timestamp (float): timestamp when this message is sent
    }
    """

    owner_id = data.get("ownerId")

    try:
        db = get_db()

        # Check READ and WRITE permission. If denied, ForbiddenProjectException is raised.
        proj_file_ctrl = await ProjectFileController.from_session(sid, db)
        proj_file_ctrl.get_target_info(target_ptc_id=owner_id, check_perm=PROJ_PERM.READ & PROJ_PERM.WRITE)

        # 해당 프로젝트 room 으로 전송
        target_room = Room.SUBS_PTC.format(
            course_id=proj_file_ctrl.course_id,
            lesson_id=proj_file_ctrl.lesson_id,
            ptc_id=owner_id,
        )
        await sio.emit(
            WSEvent.FILE_MOD,
            {
                "ptcId": await ws_session.get(sid, "participant_id"),
                "nickname": await ws_session.get(sid, "nickname"),
                "ownerId": owner_id,
                "file": data.get("file"),
                "cursor": data.get("cursor"),
                "change": data.get("change"),
                "timestamp": data.get("timestamp"),
            },
            room=target_room,
        )

    except BaseException as e:
        await sio.emit(WSEvent.FILE_MOD, ws_error_response(e.error), to=sid)


@sio.on(WSEvent.FILE_SAVE)
@requires(WSEvent.FILE_SAVE, ["ownerId", "file", "content"])
@in_lesson
async def file_save(sid: str, data: dict):
    """Save file content

    data: {
        ownerId (int): file owner's participant ID
        file (str): filename
        content (str): entire file content to save
    }
    """

    owner_id = data.get("ownerId")
    file = data.get("file")
    content = data.get("content")

    try:
        proj_file_ctrl = await ProjectFileController.from_session(sid, get_db())
        proj_file_ctrl.file_save(owner_id, file, content)

        # 해당 프로젝트 room 으로 전송
        target_room = Room.SUBS_PTC.format(
            course_id=proj_file_ctrl.course_id,
            lesson_id=proj_file_ctrl.lesson_id,
            ptc_id=owner_id,
        )
        await sio.emit(WSEvent.FILE_MOD, {"success": True}, room=target_room)
    except BaseException as e:
        await sio.emit(WSEvent.FILE_MOD, ws_error_response(e.error), to=sid)
