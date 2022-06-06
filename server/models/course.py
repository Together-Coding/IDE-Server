from __future__ import annotations
from sqlalchemy import DATETIME, Boolean, Column, ForeignKey, Integer, PrimaryKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import relationship

from server.helpers.db import Base
from server.utils.time_utils import utc_dt_now


class Course(Base):
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    password = Column(String(255), nullable=True)
    description = Column(String(255), nullable=True, default="")

    # API 서버 측의 수정으로, 컬럼이 사라짐
    # accessible = Column(Integer, nullable=False, default=True)
    # active = Column(Boolean, nullable=False, default=True)

    # API 서버 측에서, participant.role == TEACHER 인 레코드 찾는게 오래 걸려서 추가됨
    teacher_id = Column(Integer, nullable=True)

    created_at = Column(DATETIME, nullable=False, default=utc_dt_now)
    updated_at = Column(DATETIME, nullable=True, onupdate=utc_dt_now)

    participants: list[Participant] = relationship("Participant", back_populates="course")
    lessons: list[Lesson] = relationship("Lesson")


class Participant(Base):
    __tablename__ = "participants"
    __table_args__ = (UniqueConstraint("course_id", "user_id"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    role = Column(String(15), nullable=False)
    nickname = Column(String(60), nullable=False, default="")
    active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DATETIME, nullable=False, default=utc_dt_now)

    course: Course = relationship("Course", back_populates="participants", uselist=False)
    user = relationship("User", back_populates="participation", uselist=False)
    project: UserProject = relationship("UserProject", uselist=False)
    feedbacks = relationship("Feedback", back_populates="participant")
    comments = relationship("Comment", back_populates="participant")

    KEY_TEACHER = "TEACHER"
    KEY_STUDENT = "STUDENT"

    @property
    def is_teacher(self):
        return self.role == self.KEY_TEACHER

    def __repr__(self):
        return f"{type(self).__name__} id={self.id} nickname={self.nickname} ({self.role})"


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False)
    name = Column(String(255), nullable=True)
    description = Column(String(255), nullable=True)
    lesson_file_id = Column(Integer, ForeignKey("files.id"), nullable=True)
    lang_image_id = Column(Integer, nullable=False)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DATETIME, nullable=False, default=utc_dt_now)

    course: Course = relationship("Course", back_populates="lessons", uselist=False)
    file: LessonFile = relationship("LessonFile", uselist=False)
    projects: list[UserProject] = relationship("UserProject")


class LessonFile(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    url = Column(String(2048), nullable=False)  # S3 Object key
    created_at = Column(DATETIME, nullable=False, default=utc_dt_now)


class UserProject(Base):
    __tablename__ = "user_projects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False)
    participant_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    recent_activity_at = Column(DATETIME, nullable=False, default=utc_dt_now)
    active = Column(Boolean, nullable=False, default=0)
    template_applied = Column(Boolean, nullable=False, default=False)
    created_at = Column(DATETIME, nullable=False, default=utc_dt_now)

    lesson: Lesson = relationship("Lesson", back_populates="projects", uselist=False)
    participant: Participant = relationship("Participant", back_populates="project", uselist=False)
    viewers: list[ProjectViewer] = relationship("ProjectViewer")
    code_references = relationship("CodeReference")


class PROJ_PERM:
    READ: int = 0b_0000_0100
    WRITE: int = 0b_0000_0010
    EXEC: int = 0b_0000_0001
    ALL: int = 0b_0000_0111

    @staticmethod
    def translate(perm: PROJ_PERM) -> str:
        s = []
        if perm & PROJ_PERM.READ:
            s.append("읽기")
        if perm & PROJ_PERM.WRITE:
            s.append("쓰기")
        if perm & PROJ_PERM.EXEC:
            s.append("실행")

        return "/".join(s)


class ProjectViewer(Base):
    __tablename__ = "project_viewers"
    __table_args__ = (PrimaryKeyConstraint("project_id", "viewer_id"),)

    project_id = Column(Integer, ForeignKey("user_projects.id"), nullable=False)
    viewer_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    permission = Column(Integer, nullable=False, default=PROJ_PERM.READ)

    # Temporary values for the cases when the permission is changed.
    added = 0
    removed = 0

    def __repr__(self) -> str:
        return f"{type(self).__name__} project={self.project_id} viewer={self.viewer_id} perm={self.permission}"

    def has_perm(self, need_perm: PROJ_PERM) -> int:
        return self.permission & need_perm

    @property
    def read_allowed(self):
        return self.permission & PROJ_PERM.READ

    @property
    def write_allowed(self):
        return self.permission & PROJ_PERM.WRITE

    @property
    def exec_allowed(self):
        return self.permission & PROJ_PERM.EXEC
