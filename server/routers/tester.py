import datetime
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from configs import settings
from server.helpers import s3
from server.helpers.db import get_db_dep
from server.models.test import TestConfig, TestContainer


class UserEmailItem(BaseModel):
    id: int
    email: str

    class Config:
        orm_mode = True


class TestConfigResp(BaseModel):
    id: int
    course_id: int
    lesson_id: int
    server_host: str

    target_ptc_id: int | None
    start_at: datetime.datetime | None
    end_at: datetime.datetime | None
    deleted: bool

    started: bool | None
    ended: bool | None
    remaining_time: int

    class Config:
        orm_mode = True


class StartTesterBody(BaseModel):
    task_arn: str


class EndTesterBody(BaseModel):
    task_arn: str
    log: list


class EndSummaryBody(BaseModel):
    task_arn: str
    summary: Any


class TestContainerResp(BaseModel):
    test_config: TestConfigResp
    id: int
    task_arn: str
    user_id: int
    ptc_id: int
    active: bool

    user: UserEmailItem

    class Config:
        orm_mode = True


router = APIRouter(
    prefix="/admin/test",
)


@router.get("/{test_id}", response_model=TestConfigResp)
async def get_test_config(test_id: int, db: Session = Depends(get_db_dep)):
    """Return TestConfig data"""

    test: TestConfig = db.query(TestConfig).filter(TestConfig.id == test_id).first()
    return test


@router.post("/tester/start", response_model=TestContainerResp)
async def start_tester(body: StartTesterBody, db: Session = Depends(get_db_dep)):
    """When a tester initialized, return its configs"""

    tester: TestContainer = (
        db.query(TestContainer)
        .options(joinedload(TestContainer.user))
        .options(joinedload(TestContainer.test_config))
        .filter(TestContainer.task_arn == body.task_arn)
        .order_by(TestContainer.id.desc())  # If a local tester, there are multiple rows of the same task_arn
        .first()
    )

    if not tester:
        raise HTTPException(status_code=404, detail="테스터 정보를 찾을 수 없습니다.")

    tester.active = True
    tester.ping_at = datetime.datetime.utcnow()

    db.add(tester)
    db.commit()

    return tester


@router.post("/tester/end")
async def end_tester(body: EndTesterBody, db: Session = Depends(get_db_dep)):
    """When a tester is over, make it inactive and upload logs to S3"""

    tester: TestContainer = (
        db.query(TestContainer)
        .filter(TestContainer.task_arn == body.task_arn)
        .order_by(TestContainer.id.desc())  # If a local tester, there are multiple rows of the same task_arn
        .first()
    )

    if not tester:
        raise HTTPException(status_code=404, detail="테스터 정보를 찾을 수 없습니다.")

    tester.active = False
    tester.ping_at = datetime.datetime.utcnow()

    db.add(tester)
    db.commit()

    if body.log:
        task_id = body.task_arn.rsplit('/')[-1]
        stream = io.StringIO(json.dumps(body.log))
        s3.put_object(
            stream,
            key=f"test/{tester.test_config.id}/{task_id}.json",
            bucket="together-coding-dev",
        )

    return JSONResponse()


@router.post("/tester/summary")
async def end_summary(body: EndSummaryBody, db: Session = Depends(get_db_dep)):
    """
    When a tester is over, upload K6 summary data. Because teardown and summary step is divided with K6,
    uploading summary data is handled here.
    """

    # Validation
    tester: TestContainer = (
        db.query(TestContainer)
        .options(joinedload(TestContainer.test_config))
        .filter(TestContainer.task_arn == body.task_arn)
        .first()
    )

    if not tester:
        raise HTTPException(status_code=404, detail="테스터 정보를 찾을 수 없습니다.")

    # Upload to S3
    task_id = body.task_arn.rsplit('/')[-1]
    stream = io.StringIO(json.dumps(body.summary))
    s3.put_object(
        stream,
        key=f"test/{tester.test_config.id}/summary-{task_id}.json",
        bucket="together-coding-dev",
    )

    return JSONResponse()
