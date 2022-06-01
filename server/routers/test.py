import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, contains_eager, joinedload

from configs import settings
from server import templates
from server.controllers.project import ProjectController
from server.helpers import ecs
from server.helpers.db import get_db_dep
from server.models.course import Course, Lesson, Participant, ProjectViewer, PROJ_PERM, UserProject
from server.models.test import TestConfig, TestContainer
from server.models.user import User
from server.utils.etc import get_hostname


class CreateTestBody(BaseModel):
    course_id: int
    lesson_id: int
    server_host: str
    test_user_num: int
    target_ptc_id: int | None
    with_local_tester: bool


class StartTestBody(BaseModel):
    duration: int


class ModifyTestBody(BaseModel):
    server_host: str
    target_ptc_id: int | None
    duration: int | None



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

    active_test = (
        db.query(TestConfig)
        .filter(TestConfig.deleted.is_(False))
        .filter(TestConfig.active)
        .order_by(TestConfig.id.desc())
        .first()
    )

    return templates.TemplateResponse(
        "test/control_panel.html",
        {
            "request": request,
            "hostname": "Server-" + get_hostname(),
            "x_api_key": settings.WS_MONITOR_KEY,
            "course": lesson.course,
            "lesson": lesson,
            "active_test": active_test,
        },
    )


@router.post("/")
async def create_test(body: CreateTestBody, db: Session = Depends(get_db_dep)):
    """Create new TestConfig"""

    active_test: TestConfig = (
        db.query(TestConfig)
        .filter(TestConfig.deleted.is_(False))
        .filter(TestConfig.active)
        .order_by(TestConfig.id.desc())
        .first()
    )

    if active_test:
        raise HTTPException(status_code=400, detail="다른 테스트가 이미 존재합니다.")

    test_ptcs = (
        db.query(Participant)
        .join(User, User.id == Participant.user_id)
        .filter(User.email.like("testuser_%@test.com"))
        .options(contains_eager(Participant.user))
        .all()
    )

    if body.test_user_num > len(test_ptcs):
        raise HTTPException(
            status_code=400, detail=f"최대 {len(test_ptcs)} 만큼의 머신을 사용할 수 있습니다. 테스트 계정을 추가하여 제한을 높일 수 있습니다."
        )

    if body.test_user_num == 0 and not body.with_local_tester:
        raise HTTPException(status_code=400, detail="머신 개수를 입력하거나 로컬 테스터를 선택해주세요.")

    tc = TestConfig(
        course_id=body.course_id,
        lesson_id=body.lesson_id,
        server_host=body.server_host,
        target_ptc_id=body.target_ptc_id or None,
        test_user_num=body.test_user_num,
    )
    db.add(tc)
    db.flush()

    task_arns = ecs.run_task(num=body.test_user_num, started_by=get_hostname())

    for idx, task_arn in enumerate(task_arns):
        test_ptc: Participant = test_ptcs[idx]
        db.add(
            TestContainer(
                test_id=tc.id,
                task_arn=task_arn,
                user_id=test_ptc.user.id,
                ptc_id=test_ptc.id,
            )
        )

    if body.with_local_tester:
        db.add(
            TestContainer(
                test_id=tc.id,
                task_arn="127.0.0.1",
                user_id=test_ptcs[0].user.id,
                ptc_id=test_ptcs[0].id,
            )
        )

    db.commit()

    return JSONResponse(status_code=200, content="테스트가 생성되었습니다.")


@router.post("/{test_id}")
async def start_test(test_id: int, body: StartTestBody, db: Session = Depends(get_db_dep)):
    """Set TestConfig.start_at"""

    test: TestConfig = (
        db.query(TestConfig)
        .filter(TestConfig.id == test_id)
        .filter(TestConfig.deleted.is_(False))
        .filter(TestConfig.active)
        .first()
    )

    if not test:
        raise HTTPException(status_code=404, detail="해당 테스트를 수정할 수 없습니다. 테스트의 상태를 확인해주세요.")

    test.start_at = datetime.datetime.utcnow()
    test.end_at = test.start_at + datetime.timedelta(minutes=body.duration)
    db.add(test)

    # test.target_ptc_id 가 있는 경우, 생성 되어있는 모든 cont 의 유저가 해당 ptc 에
    #  접근 가능하도록 ProjectViewer 추가
    if test.target_ptc_id:
        target_ptc: Participant = db.query(Participant).filter(Participant.id == test.target_ptc_id).first()
        proj_ctrl = ProjectController(
            course_id=test.course_id, lesson_id=test.lesson_id, user_id=target_ptc.user_id, db=db
        )
        target_proj = proj_ctrl.create_if_not_exists()

        for tester in test.testers:
            db.add(
                ProjectViewer(
                    project_id=target_proj.id,
                    viewer_id=tester.ptc_id,
                    permission=PROJ_PERM.ALL,
                )
            )

    db.commit()

    return JSONResponse(status_code=200)


@router.put("/{test_id}")
async def modify_test(test_id: int, body: ModifyTestBody, db: Session = Depends(get_db_dep)):
    """Modify TestConfig"""

    test: TestConfig = (
        db.query(TestConfig)
        .filter(TestConfig.id == test_id)
        .filter(TestConfig.deleted.is_(False))
        .filter(TestConfig.active)
        .first()
    )

    if not test:
        raise HTTPException(status_code=404, detail="해당 테스트를 수정할 수 없습니다. 테스트의 상태를 확인해주세요.")

    if test.ended:
        raise HTTPException(status_code=400, detail="테스트가 종료되어, 수정할 수 없습니다.")

    target_ptc_id = body.target_ptc_id or None
    duration = body.duration

    if test.started and target_ptc_id != test.target_ptc_id:
        raise HTTPException(status_code=400, detail="테스트가 시작되어, 대상 PTC ID 를 수정할 수 없습니다.")
    elif test.started and body.server_host != test.server_host:
        raise HTTPException(status_code=400, detail="테스트가 시작되어, Server Host 를 수정할 수 없습니다.")

    test.target_ptc_id = target_ptc_id
    test.server_host = body.server_host

    if duration and duration <= 0:
        raise HTTPException(status_code=400, detail="추가 시간 값이 잘못 되었습니다.")

    if duration and test.end_at:
        test.end_at += datetime.timedelta(minutes=duration)

    db.add(test)
    db.commit()

    return JSONResponse(status_code=200)


@router.delete("/{test_id}")
async def delete_test(test_id: int, db: Session = Depends(get_db_dep)):
    """Delete TestConfig"""

    test: TestConfig = (
        db.query(TestConfig).filter(TestConfig.id == test_id).filter(TestConfig.deleted.is_(False)).first()
    )

    if not test:
        raise HTTPException(status_code=404, detail="테스트를 찾을 수 없습니다.")

    test.deleted = True
    db.add(test)
    db.commit()

    return JSONResponse(status_code=200)
