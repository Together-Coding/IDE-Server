from constants.ws import Room, WSEvent
from server import sio
from server.controllers.cursor import CursorController
from server.controllers.project import ProjectFileController
from server.helpers import sentry
from server.helpers.db import get_db
from server.models.course import PROJ_PERM
from server.utils.exceptions import BaseException, MissingFieldException
from server.utils.response import ws_error_response
from server.websockets import session as ws_session
from server.websockets.decorators import in_lesson, requires


@sio.on(WSEvent.CURSOR_LAST)
@requires(WSEvent.CURSOR_LAST, ["ownerId", "file"])
@in_lesson
async def get_last_cursor(sid: str, data: dict):
    """
    Return user's previous cursor on the owner's file.

    data: {
        ownerId (int): owner user's participant ID
        file (str): filename
    }
    """

    owner_id: int = data.get("ownerId")
    file: str = data.get("file")

    try:
        db = get_db()

        # Check READ permission. If no permission, ForbiddenProjectException exception occurs.
        proj_file_ctrl: ProjectFileController = await ProjectFileController.from_session(sid=sid, db=db)
        proj_file_ctrl.get_target_info(target_ptc_id=owner_id, check_perm=PROJ_PERM.READ)

        cursor_ctrl: CursorController = await CursorController.from_session(sid=sid, db=db)
        cursor = cursor_ctrl.get_last_cursor(owner_id, file)

        await sio.emit(
            WSEvent.CURSOR_LAST,
            {
                "ownerId": owner_id,
                "file": file,
                "cursor": cursor,
            },
            to=sid,
        )
    except BaseException as e:
        await sio.emit(WSEvent.CURSOR_LAST, ws_error_response(e.error), to=sid)


@sio.on(WSEvent.CURSOR_MOVE)
@requires(WSEvent.CURSOR_MOVE, ["fileInfo", "timestamp"])
@in_lesson
async def update_last_cursor(sid: str, data: dict):
    """
    Update last cursor position
    """

    file_info: dict = data.get("fileInfo")
    timestamp: float = data.get("timestamp")
    event: str | None = data.get("event")

    try:
        # Validation
        if type(file_info) != dict:
            raise MissingFieldException("`fileInfo` must be an object type.")

        errs = []
        file_info_keys = ["ownerId", "file", "line", "cursor"]

        for key in file_info_keys:
            if key not in file_info.keys():
                errs.append(f"`fileInfo.{key}` is required.")
        if errs:
            raise MissingFieldException(errs)

        owner_id = file_info["ownerId"]
        file = file_info["file"]
        line = file_info["line"]
        cursor = file_info["cursor"]

        # FIXME: 프로젝트에 브로드캐스트
        await sio.emit(
            WSEvent.CURSOR_MOVE,
            {
                "userId": await ws_session.get(sid, "user_id"),
                "nickname": await ws_session.get(sid, "nickname"),
                "fileInfo": {
                    "ownerId": owner_id,
                    "file": file,
                    "line": line,
                    "cursor": cursor,
                },
                "timestamp": timestamp,
            },
            to=sid,
        )
        
        # If the event is 'open', do not need to update it, but need to broadcast the cursor.
        if event != "open":
            # Check READ permission. If no permission, ForbiddenProjectException exception occurs.
            db = get_db()
            proj_file_ctrl: ProjectFileController = await ProjectFileController.from_session(sid=sid, db=db)
            proj_file_ctrl.get_target_info(target_ptc_id=owner_id, check_perm=PROJ_PERM.READ)

            cursor_ctrl: CursorController = await CursorController.from_session(sid=sid, db=db)
            cursor_ctrl.update_last_cursor(owner_id, file, cursor)
    except MissingFieldException as e:
        await sio.emit(WSEvent.CURSOR_MOVE, ws_error_response(e.error), to=sid)
    except BaseException as e:
        await sio.emit(WSEvent.CURSOR_MOVE, ws_error_response(e.error), to=sid)
