from constants.ws import Room, WSEvent
from server import sio
from server.controllers.project import PingController, ProjectController
from server.helpers.db import get_db
from server.models.course import PROJ_PERM
from server.utils import serializer
from server.websockets import session as ws_session


@sio.on(WSEvent.INIT_LESSON)
async def init_lesson(sid: str, data=None):
    """Initialize lesson websocket session"""

    errs = []
    course_id = data.get("courseId")
    lesson_id = data.get("lessonId")

    if not course_id:
        errs.append("`courseId` is required.")
    elif not lesson_id:
        errs.append("`lessonId` is required.")

    if errs:
        return await sio.emit(WSEvent.INIT_LESSON, data={"success": False, "error": errs}, to=sid)

    # 유저의 수업 정보 저장
    await ws_session.update(sid, {"course_id": course_id, "lesson_id": lesson_id})

    # 수업 room 에 추가
    await ws_session.enter_room(sid, "lesson", Room.LESSON.format(course_id=course_id, lesson_id=lesson_id), 1)

    # 개별 participant room 에 추가
    proj_ctrl: ProjectController = await ProjectController.from_session(sid, get_db())
    ws_session.enter_ptc_id_room(sid, proj_ctrl.my_participant.id)

    await sio.emit(WSEvent.INIT_LESSON, data={"success": True}, to=sid)


@sio.on(WSEvent.ACTIVITY_PING)
async def ping(sid: str, data=None):
    """Listen ping to update UserProject.recent_activity_at"""

    user_id: int = await ws_session.get(sid, "user_id")
    course_id: int = await ws_session.get(sid, "course_id")
    lesson_id: int = await ws_session.get(sid, "lesson_id")

    ctrl = PingController(user_id=user_id, course_id=course_id, lesson_id=lesson_id, db=get_db())
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
        userId: (int) target user's participant ID
        permission: (int) new RWX permission
    }
    """

    proj_ctrl = await ProjectController.from_session(sid, get_db())
    if type(data) != list:
        return await sio.emit(WSEvent.PROJECT_PERM, {"success": False, "error": "list type is expected."}, to=sid)

    modified_noti = []
    for d in data:
        try:
            row = proj_ctrl.modify_project_permission(d["userId"], d["permission"])
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
        await sio.emit(WSEvent.PROJECT_PERM, noti, room=ptc_room)

    await sio.emit(WSEvent.PROJECT_PERM, {"success": True, "error": "Permission changed."}, to=sid)
