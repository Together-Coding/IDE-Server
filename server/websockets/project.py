from constants.ws import Room, WSEvent
from server import sio
from server.controllers.project import PingController, ProjectController, ProjectFileController
from server.helpers import sentry
from server.helpers.db import get_db
from server.models.course import PROJ_PERM
from server.utils import serializer
from server.utils.exceptions import BaseException
from server.utils.response import ws_error_response
from server.websockets.main import requires
from server.websockets.course import in_lesson


@sio.on(WSEvent.ACTIVITY_PING)
@in_lesson
async def ping(sid: str, data=None):
    """Listen ping to update UserProject.recent_activity_at"""

    ctrl = await PingController.from_session(sid, get_db())
    ctrl.update_recent_activity()

    await sio.emit(WSEvent.ACTIVITY_PING, "pong", to=sid)


@sio.on(WSEvent.PROJECT_ACCESSIBLE)
@in_lesson
async def project_accessible(sid: str, data=None):
    """
    1. 내가 접근 가능한 프로젝트들의 소유자
    2. 나의 프로젝트에 접근 가능한 유저
    이들과 관련된 데이터를 반환한다.
    """

    proj_ctrl = await ProjectController.from_session(sid, get_db())
    to_users = proj_ctrl.accessible_to()
    from_users = proj_ctrl.accessed_by()

    resp = {
        "accessible_to": [serializer.accessible_user(part, proj, perm) for part, proj, perm in to_users],
        "accessed_by": [serializer.accessible_user(part, proj, perm) for part, proj, perm in from_users],
    }
    await sio.emit(WSEvent.PROJECT_ACCESSIBLE, resp, to=sid)


@sio.on(WSEvent.PROJECT_PERM)
@in_lesson
async def modify_project_permission(sid: str, data=None):
    """나의 프로젝트에 대한 각 유저의 권한 변경

    data: {
        targetId: (int) target user's participant ID
        permission: (int) new RWX permission
    }
    """

    proj_ctrl = await ProjectController.from_session(sid, get_db())
    if type(data) != list:
        return await sio.emit(WSEvent.PROJECT_PERM, ws_error_response("list type is expected."), to=sid)

    modified_noti = []
    for d in data:
        try:
            row = proj_ctrl.modify_project_permission(d["targetId"], d["permission"])
            if not row:
                continue

            # TODO: READ 권한이 제거되었다면, 요청한 유저에 대해 구독중인 room 을 나간다.
            if row.removed & PROJ_PERM.READ:
                pass

            modified_noti.append(serializer.permission_modified(proj_ctrl.my_participant.id, row))
        except KeyError:
            continue

    for noti in modified_noti:
        # 권한이 변경된 유저들에게 알림을 전송한다.
        ptc_room = Room.PERSONAL_PTC.format(ptc_id=noti["userId"])
        await sio.emit(WSEvent.PROJECT_PERM_CHANGED, noti, room=ptc_room)

    await sio.emit(WSEvent.PROJECT_PERM, {"message": "Permission changed."}, to=sid)


@sio.on(WSEvent.DIR_INFO)
@requires(WSEvent.DIR_INFO, ["targetId"])
@in_lesson
async def get_dir_info(sid: str, data: dict | None = None):
    """``targetId` 에 해당하는 Participant 의 directory, file 리스트를 반환한다.

    data: {
        targetId: (int) target user's participant ID
    }
    """
    target_id = data.get("targetId")

    try:
        proj_file_ctrl = await ProjectFileController.from_session(sid=sid, db=get_db())
        files = proj_file_ctrl.get_dir_info(target_id)

        await sio.emit(WSEvent.DIR_INFO, {"file": files}, to=sid)
    except BaseException as e:
        return await sio.emit(WSEvent.DIR_INFO, ws_error_response(e.error), to=sid)
    except Exception as e:
        sentry.exc()
        return await sio.emit(WSEvent.DIR_INFO, ws_error_response("Unknown error occurred."), to=sid)


@sio.on(WSEvent.FILE_READ)
@requires(WSEvent.FILE_READ, ["ownerId", "file"])
@in_lesson
async def file_read(sid: str, data: dict):
    """Return file content of the owner

    data: {
        ownerId: (int) owner user's participant ID
        file: (str) file name to read
    }
    """
    owner_id = data.get("ownerId")
    file = data.get("file", "").strip("/")

    try:
        proj_file_ctrl = await ProjectFileController.from_session(sid=sid, db=get_db())
        content = proj_file_ctrl.get_file_content(owner_id, file)
        await sio.emit(WSEvent.FILE_READ, {"ownerId": owner_id, "file": file, "content": content}, to=sid)
    except BaseException as e:
        return await sio.emit(WSEvent.FILE_READ, ws_error_response(e.error), to=sid)


@sio.on(WSEvent.FILE_CREATE)
@requires(WSEvent.FILE_CREATE, ["ownerId", "type", "name"])
@in_lesson
async def file_create(sid: str, data: dict):
    """Create file or directory

    data: {
        ownerId: (int) owner user's participant ID
        type: (str) "file" or "directory"
        name: (str) file or directory name to create
    }
    """

    owner_id = data.get("ownerId")
    type_ = data.get("type")
    name = data.get("name", "").strip("/")

    try:
        proj_file_ctrl = await ProjectFileController.from_session(sid=sid, db=get_db())
        proj_file_ctrl.create_file_or_dir(owner_id, type_, name)
        # FIXME: 해당 프로젝트 room 으로 전송
        await sio.emit(WSEvent.FILE_CREATE, {"type": type_, "name": name}, to=sid)
    except BaseException as e:
        return await sio.emit(WSEvent.FILE_CREATE, ws_error_response(e.error), to=sid)


@sio.on(WSEvent.FILE_UPDATE)
@requires(WSEvent.FILE_UPDATE, ["ownerId", "type", "name", "rename"])
@in_lesson
async def file_update(sid: str, data: dict):
    """Update file or directory name

    data: {
        ownerId: (int) owner user's participant ID
        type: (str) "file" or "directory"
        name: (str) file or directory name to change
        rename: (str) changed name
    }
    """

    owner_id = data.get("ownerId")
    type_ = data.get("type")
    name = data.get("name", "").strip("/")
    rename = data.get("rename", "").strip("/")

    try:
        proj_file_ctrl = await ProjectFileController.from_session(sid=sid, db=get_db())
        proj_file_ctrl.update_file_or_dir_name(owner_id, type_, name, rename)
        # FIXME: 해당 프로젝트 room 으로 전송
        await sio.emit(
            WSEvent.FILE_UPDATE,
            {
                "ownerId": owner_id,
                "type": type_,
                "name": name,
                "rename": rename,
            },
            to=sid,
        )
    except BaseException as e:
        return await sio.emit(WSEvent.FILE_UPDATE, ws_error_response(e.error), to=sid)


@sio.on(WSEvent.FILE_DELETE)
@requires(WSEvent.FILE_DELETE, ["ownerId", "type", "name"])
@in_lesson
async def file_delete(sid: str, data: dict):
    """Delete file or directory

    data: {
        ownerId (int): owner user's participant ID
        type: (str) "file" or "directory"
        name (str): file or directory name to delete
    }
    """

    owner_id = data.get("ownerId")
    type_ = data.get("type")
    name = data.get("name", "").strip("/")

    try:
        proj_file_ctrl = await ProjectFileController.from_session(sid=sid, db=get_db())
        proj_file_ctrl.delete_file_or_dir(owner_id, type_, name)

        # FIXME: 해당 프로젝트 room 으로 전송
        await sio.emit(
            WSEvent.FILE_DELETE,
            {
                "ownerId": owner_id,
                "type": type_,
                "name": name,
            },
            to=sid,
        )
    except BaseException as e:
        return await sio.emit(WSEvent.FILE_DELETE, ws_error_response(e.error), to=sid)
