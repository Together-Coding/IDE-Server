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


@sio.on(WSEvent.ACTIVITY_PING)
async def ping(sid: str, data=None):
    """Listen ping to update UserProject.recent_activity_at"""

    ctrl = await PingController.from_session(sid, get_db())
    ctrl.update_recent_activity()

    await sio.emit(WSEvent.ACTIVITY_PING, "pong", to=sid)


@sio.on(WSEvent.PROJECT_ACCESSIBLE)
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
async def get_dir_info(sid: str, data: dict | None = None):
    """``targetId` 에 해당하는 Participant 의 directory, file 리스트를 반환한다.

    data: {
        targetId: (int) target user's participant ID
    }
    """
    target_ptc_id = data.get("targetId")

    try:
        proj_file_ctrl = await ProjectFileController.from_session(sid=sid, db=get_db())
        files = proj_file_ctrl.get_dir_info(target_ptc_id)
        await sio.emit(WSEvent.DIR_INFO, {"file": files}, to=sid)
    except BaseException as e:
        return await sio.emit(WSEvent.DIR_INFO, ws_error_response(e.error), to=sid)
    except Exception as e:
        sentry.exc()
        return await sio.emit(WSEvent.DIR_INFO, ws_error_response("Unknown error occurred."), to=sid)


@sio.on(WSEvent.FILE_READ)
@requires(WSEvent.FILE_READ, ["ownerId", "file"])
async def file_read(sid: str, data: dict):
    """

    data: {
        ownerId: (int) owner user's participant ID
        file: (str) file name to read
    }
    """
    owner_id = data.get("ownerId")
    file = data.get("file")

    try:
        proj_file_ctrl = await ProjectFileController.from_session(sid=sid, db=get_db())
        content = proj_file_ctrl.get_file_content(owner_id, file)
        await sio.emit(WSEvent.FILE_READ, {"ownerId": owner_id, "file": file, "content": content}, to=sid)
    except BaseException as e:
        return await sio.emit(WSEvent.DIR_INFO, ws_error_response(e.error), to=sid)
