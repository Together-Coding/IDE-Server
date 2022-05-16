from sqlalchemy.orm import Session

from server.controllers.file import RedisController, S3Controller
from server.models.course import Lesson, Participant, UserProject
from server.websockets import session as ws_session


class BaseContoller:
    def __init__(self, db: Session | None = None, *args, **kwargs):
        self.db = db


class CourseBaseController(BaseContoller):
    def __init__(self, course_id: int, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.course_id = course_id


class LessonBaseController(CourseBaseController):
    def __init__(self, lesson_id: int, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.lesson_id = lesson_id

        self.redis_ctrl = RedisController(self.course_id, self.lesson_id)
        self.s3_ctrl = S3Controller(self.course_id, self.lesson_id, self.redis_ctrl.redis_key)


class LessonUserController(LessonBaseController):
    def __init__(
        self,
        user_id: int,
        participant: Participant | None = None,
        project: UserProject | None = None,
        lesson: Lesson | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.user_id = user_id

        self._participant = participant
        self._project = project
        self._lesson = lesson

    @classmethod
    async def from_session(cls, sid: str, db: Session):
        """Create ProjectController from websocket session data

        Args:
            sid (str): socketio session
            db (Session): database session

        Returns:
            ProjectController:
        """
        user_id: int = await ws_session.get(sid, "user_id")
        course_id: int = await ws_session.get(sid, "course_id")
        lesson_id: int = await ws_session.get(sid, "lesson_id")

        return cls(user_id=user_id, course_id=course_id, lesson_id=lesson_id, db=db)

    @property
    def my_participant(self) -> Participant:
        if not self._participant:
            self._participant = (
                self.db.query(Participant)
                .filter(Participant.course_id == self.course_id)
                .filter(Participant.user_id == self.user_id)
                .first()
            )

        return self._participant

    @property
    def my_project(self) -> UserProject:
        """Return participant's UserProject"""

        if not self.my_participant:
            return

        if not self._project:
            self._project = (
                self.db.query(UserProject)
                .filter(UserProject.lesson_id == self.lesson_id)
                .filter(UserProject.participant_id == self.my_participant.id)
                .first()
            )

        return self._project

    @property
    def my_lesson(self) -> Lesson:
        """Return Lesson from self.lesson_id"""

        if not self.lesson_id:
            return

        if not self._lesson:
            self._lesson = self.db.query(Lesson).filter(Lesson.id == self.lesson_id).first()

        return self._lesson
