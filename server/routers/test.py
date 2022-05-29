from collections import defaultdict
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload, contains_eager

from configs import settings
from server import templates
from server.helpers.db import get_db, get_db_dep
from server.models.course import Course, Lesson
from server.models.test import TestConfig, TestContainer


def auth_required(api_key: str = Header(default="", alias="X-API-KEY")):
    if api_key != settings.WS_MONITOR_KEY:
        raise HTTPException(status_code=403, detail="X-API-KEY is invalid.")


router = APIRouter(
    prefix="/admin/test",
    dependencies=[Depends(auth_required)],
)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db_dep)):
    courses = (
        db.query(Course)
        .join(Lesson, Lesson.course_id == Course.id)
        .options(contains_eager(Course.lessons))
        .order_by(Course.id.desc())
        .order_by(Lesson.id.asc())
        .all()
    )

    return templates.TemplateResponse(
        "test/lesson_list.html",
        {
            "request": request,
            "courses": courses,
        },
    )


@router.get("/control-panel", response_class=HTMLResponse)
async def control_panel(
    request: Request,
    course_id: int,
    lesson_id: int,
    db: Session = Depends(get_db_dep),
):
    lesson = db.query(Lesson).filter(Lesson.course_id == course_id).filter(Lesson.id == lesson_id).first()

    if not lesson:
        raise HTTPException(status_code=404, detail="존재하지 않는 수업입니다.")

    return templates.TemplateResponse(
        "test/control_panel.html",
        {
            "request": request,
            "x_api_key": settings.WS_MONITOR_KEY,
            "lesson": lesson,
        },
    )


@router.get("/ttest", response_class=HTMLResponse)
async def ttest(request: Request):
    return templates.TemplateResponse("test/d3_test.html", {"request": request})
