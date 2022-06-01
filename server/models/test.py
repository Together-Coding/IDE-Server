from __future__ import annotations

import datetime

from sqlalchemy import DATETIME, TEXT, Boolean, Column, ForeignKey, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from server.helpers.db import Base
from server.utils.time_utils import utc_dt_now


class TestConfig(Base):
    __tablename__ = "test_config"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    course_id = Column(Integer, ForeignKey("courses.id"), nullable=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=True)

    server_host = Column(TEXT, nullable=False)

    # Target participant ID that the test users are interact with. If null, interact with random user.
    target_ptc_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Number of test containers
    test_user_num = Column(Integer, nullable=False)

    start_at = Column(DATETIME, nullable=True)
    end_at = Column(DATETIME, nullable=True)
    deleted = Column(Boolean, nullable=False, default=False)

    testers: list[TestContainer] = relationship("TestContainer")

    @hybrid_property
    def active(self):
        return self.end_at.is_(None) | (self.end_at > datetime.datetime.utcnow())

    @property
    def started(self):
        return self.start_at and datetime.datetime.utcnow() > self.start_at

    @property
    def ended(self):
        return self.end_at and datetime.datetime.utcnow() > self.end_at

    @property
    def remaining_time(self) -> int:
        if not (self.start_at and self.end_at):
            return 0

        return int((self.end_at - datetime.datetime.utcnow()).total_seconds())

class TestContainer(Base):
    __tablename__ = "test_container"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    test_id = Column(Integer, ForeignKey("test_config.id"), nullable=False)
    task_arn = Column(TEXT, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ptc_id = Column(Integer, ForeignKey("participants.id"), nullable=True)

    active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DATETIME, nullable=False, default=utc_dt_now)
    ping_at = Column(DATETIME, nullable=True)

    test_config: TestConfig = relationship("TestConfig", uselist=False)
    user = relationship("User", uselist=False)
    participant = relationship("Participant", uselist=False)

    @property
    def has_recent_ping(self):
        return bool(self.ping_at) and (self.ping_at + datetime.timedelta(seconds=5) > datetime.datetime.utcnow())
