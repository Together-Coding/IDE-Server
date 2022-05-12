from constants.ws import Room, WSEvent
from server import sio
from server.controllers.project import ProjectController
from server.helpers.db import get_db
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

    # 수업 정보 저장
    await ws_session.update(sid, {"course_id": course_id, "lesson_id": lesson_id})

    # 수업 room 에 추가
    await ws_session.enter_room(sid, "lesson", Room.LESSON.format(course_id=course_id, lesson_id=lesson_id), 1)

    # UserProject 없으면 생성
    proj_ctrl: ProjectController = await ProjectController.from_session(sid, get_db())

    # 개별 participant room 에 추가
    ws_session.enter_ptc_id_room(sid, proj_ctrl.my_participant.id)

    # Participant ID 저장
    await ws_session.update(sid, {"participant_id": proj_ctrl.my_participant.id})

    await sio.emit(WSEvent.INIT_LESSON, data={"success": True}, to=sid)
