import functools
from typing import Awaitable
from constants.ws import Room, WSEvent
from server import sio
from server.controllers.project import ProjectController
from server.helpers.db import get_db
from server.utils.response import ws_error_response
from server.websockets import session as ws_session
from server.websockets.main import requires


def in_lesson(f: Awaitable):
    """
    Users must initialize a lesson first by INIT_LESSON event.
    If uninitialized user requests the decorated event handler, do not execute
    the handler and respond with error reason.
    """

    async def decorated(sid: str, *args, **kwargs):
        course_id: int = await ws_session.get(sid, "course_id")
        lesson_id: int = await ws_session.get(sid, "lesson_id")

        if not course_id or not lesson_id:
            msg = "수업에 접속한 상태가 아닙니다. `INIT_LESSON` 이벤트를 전송해주세요."
            return await sio.emit(WSEvent.ERROR, ws_error_response(msg), to=sid)

        return await f(sid, *args, **kwargs)

    return decorated


@sio.on(WSEvent.INIT_LESSON)
@requires(WSEvent.INIT_LESSON, ["courseId", "lessonId"])
async def init_lesson(sid: str, data: dict):
    """Initialize lesson websocket session"""

    course_id = data.get("courseId")
    lesson_id = data.get("lessonId")

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
