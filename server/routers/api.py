"""
Because of lack of time, APIs below are alternative to the supposed-to-be API server's
"""

import datetime

from fastapi import APIRouter, Depends, Header, Request
from fastapi.exceptions import HTTPException
from server.utils.response import api_response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from server.controllers.user import AuthController
from server.helpers.db import get_db_dep
from server.models.course import Course, Lesson


def auth_required(request: Request, auth: str = Header(default="Bearer ", alias="Authorization")):
    idx = auth.lower().find("bearer")
    if idx != -1:
        token = auth[idx + len("bearer") :].strip()
    else:
        token = ""

    success, token_info = AuthController.verify_token(token)

    # If non-valid token
    if not success:
        raise HTTPException(status_code=403, detail=token_info["error"])

    request.state.user = token_info


router = APIRouter(
    prefix="/api",
    dependencies=[Depends(auth_required)],
)


class GetLessonResp(BaseModel):
    id: int
    course_id: int
    name: str | None
    description: str | None
    lesson_file_id: int | None
    lang_image_id: int
    active: bool
    created_at: datetime.datetime

    class Config:
        orm_mode = True


@router.get("/lesson/{lesson_id}", response_model=GetLessonResp)
async def get_lesson(lesson_id: int, db: Session = Depends(get_db_dep)):
    lesson: Lesson = db.query(Lesson).filter(Lesson.id == lesson_id).first()

    if not lesson:
        return api_response("수업을 찾을 수 없습니다.", status_code=404)

    return lesson


class ProjectFileResp(BaseModel):
    files: list


@router.post("/{course_id}/{lesson_id}/{ptc_id}")
async def get_project_file(course_id: int, lesson_id: int, ptc_id: int, db: Session = Depends(get_db_dep)):
    from server.controllers.file import RedisController
    from server.helpers.redis_ import r
    from server.utils.etc import text_decode

    redis_ctrl = RedisController(course_id=course_id, lesson_id=lesson_id, r_=r)
    enc_filenames = redis_ctrl.get_file_list(ptc_id)

    files = {text_decode(enc_filename): redis_ctrl.get_file(enc_filename, ptc_id, hashed=False) for enc_filename in enc_filenames}

    return files
