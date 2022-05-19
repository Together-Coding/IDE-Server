from constants.ws import Room, WSEvent
from server import sio
from server.controllers.course import CourseUserController
from server.controllers.lesson import LessonBaseController
from server.utils.exceptions import AccessCourseFailException
from server.utils.response import ws_error_response
from server.helpers.db import get_db
from server.websockets import session as ws_session
from server.websockets.decorators import requires


@sio.on(WSEvent.INIT_LESSON)
@requires(WSEvent.INIT_LESSON, ["courseId", "lessonId"])
async def init_lesson(sid: str, data: dict):
    """Initialize lesson websocket session"""

    user_id = await ws_session.get(sid, "user_id")
    course_id = data.get("courseId")
    lesson_id = data.get("lessonId")

    db = get_db()

    # 수업 접근 가능 여부 확인
    try:
        course_ctrl = CourseUserController(user_id=user_id, course_id=course_id, db=db)
        course_ctrl.check_accessibility()
    except AccessCourseFailException as e:
        # Not accessible, then return function with error message
        return await sio.emit(WSEvent.INIT_LESSON, ws_error_response(e.error), to=sid)

    # 강의 접근 가능 여부 확인
    lesson_ctrl = LessonBaseController(course_id=course_id, lesson_id=lesson_id, db=db)
    if lesson_ctrl.my_lesson is None:
        return await sio.emit(WSEvent.INIT_LESSON, ws_error_response("존재하지 않는 강의입니다."), to=sid)

    # 수업 정보 저장
    await ws_session.update(sid, {"course_id": course_id, "lesson_id": lesson_id})

    # 수업 room 에 추가
    await ws_session.enter_room(sid, "lesson", Room.LESSON.format(course_id=course_id, lesson_id=lesson_id), 1)

    # 개별 participant room 에 추가
    ws_session.enter_ptc_id_room(sid, course_ctrl.my_participant.id)

    # Participant ID 저장
    await ws_session.update(
        sid,
        {
            "participant_id": course_ctrl.my_participant.id,
            "nickname": course_ctrl.my_participant.nickname,
        },
    )

    await sio.emit(WSEvent.INIT_LESSON, data={"success": True}, to=sid)
