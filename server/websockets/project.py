from constants.ws import Room, WSEvent
from server import sio
from server.controllers.project import PingController, ProjectController
from server.helpers.db import get_db
from server.utils import serializer
from server.websockets import session as ws_session


@sio.on(WSEvent.INIT_LESSON)
async def init_lesson(sid, data=None):
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

    # 유저를 ROOM 에 추가
    await ws_session.enter_room(sid, "lesson", Room.LESSON.format(course_id=course_id, lesson_id=lesson_id), 1)

    await sio.emit(WSEvent.INIT_LESSON, data={"success": True}, to=sid)


@sio.on(WSEvent.ACTIVITY_PING)
async def ping(sid, data=None):
    """Listen ping to update UserProject.recent_activity_at"""

    user_id: int = await ws_session.get(sid, "user_id")
    course_id: int = await ws_session.get(sid, "course_id")
    lesson_id: int = await ws_session.get(sid, "lesson_id")

    ctrl = PingController(user_id=user_id, course_id=course_id, lesson_id=lesson_id, db=get_db())
    ctrl.update_recent_activity()

    await sio.emit(WSEvent.ACTIVITY_PING, "pong", to=sid)


@sio.on(WSEvent.PROJECT_ACCESSIBLE)
async def project_accessible(sid, data=None):
    """
    1. 내가 접근 가능한 프로젝트들의 소유자
    2. 나의 프로젝트에 접근 가능한 유저
    이들과 관련된 데이터를 반환한다.
    """

    proj_ctrl: ProjectController = await ProjectController.from_session(sid, get_db())
    to_users = proj_ctrl.accessible_to()
    from_users = proj_ctrl.accessed_by()

    data = {
        "accessible_to": [serializer.accessible_user(part, proj, perm) for part, proj, perm in to_users],
        "accessed_by": [serializer.accessible_user(part, proj, perm) for part, proj, perm in from_users],
    }
    await sio.emit(WSEvent.PROJECT_ACCESSIBLE, data, to=sid)
