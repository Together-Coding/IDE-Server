from constants.ws import Room, WSEvent
from server import sio
from server.controllers.project import ProjectController
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

    # 수업 정보 저장
    await ws_session.update(sid, {"course_id": course_id, "lesson_id": lesson_id})

    # 수업 접근 가능 여부 확인
    proj_ctrl = ProjectController(user_id=user_id, course_id=course_id, lesson_id=lesson_id, db=get_db())
    try:
        proj_ctrl.check_accessibility()
    except AccessCourseFailException as e:
        # Not accessible, then return function with error message
        return await sio.emit(WSEvent.INIT_LESSON, ws_error_response(e.error), to=sid)

    # 강의 접근 가능 여부 확인
    if proj_ctrl.my_lesson is None:
        return await sio.emit(WSEvent.INIT_LESSON, ws_error_response("존재하지 않는 강의입니다."), to=sid)

    # Participant ID 저장
    ptc = proj_ctrl.my_participant
    await ws_session.update(
        sid,
        {
            "participant_id": ptc.id,
            "nickname": ptc.nickname,
        },
    )

    # 수업 room 에 추가
    await ws_session.enter_room(
        sid,
        WSEvent.INIT_LESSON,
        Room.LESSON.format(course_id=course_id, lesson_id=lesson_id),
        limit=1,
    )

    # 개별 유저의 room 에 추가
    ws_session.enter_ptc_id_room(sid, course_id, lesson_id, ptc.id)

    # 자기 자신으로의 구독
    room_name = Room.SUBS_PTC.format(course_id=course_id, lesson_id=lesson_id, ptc_id=ptc.id)
    await ws_session.enter_room(sid, room_type=WSEvent.SUBS_PARTICIPANT, new_room=room_name)

    # Read 권한이 있어서, 접근할 수 있는 유저들 구독
    for target_ptc, _, _ in proj_ctrl.accessible_to():
        room_name = Room.SUBS_PTC.format(
            course_id=course_id,
            lesson_id=lesson_id,
            ptc_id=target_ptc.id,
        )
        await ws_session.enter_room(sid, room_type=WSEvent.SUBS_PARTICIPANT, new_room=room_name)

    await sio.emit(WSEvent.INIT_LESSON, data={"success": True}, to=sid)
