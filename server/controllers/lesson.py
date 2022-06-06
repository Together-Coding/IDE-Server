from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from constants.ws import WSEvent, Room
from server import sio
from server.controllers.course import CourseBaseController, CourseUserController
from server.controllers.file import RedisController, S3Controller
from server.models.course import Lesson, Participant, UserProject
from server.websockets import session as ws_session
from server.utils import serializer
from server.helpers.cache import course_cache, lesson_cache


class LessonBaseController(CourseBaseController):
    def __init__(
        self,
        lesson_id: int,
        lesson: Lesson | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.lesson_id = lesson_id

        self._lesson = lesson

        self.redis_ctrl = RedisController(self.course_id, self.lesson_id)
        self.s3_ctrl = S3Controller(self.course_id, self.lesson_id, self.redis_ctrl.redis_key)

    @lesson_cache.memoize(timeout=60)
    def get_lesson(self, lesson_id: int):
        return self.db.query(Lesson).options(joinedload(Lesson.file)).filter(Lesson.id == lesson_id).first()

    @property
    def my_lesson(self) -> Lesson:
        """Return Lesson from self.lesson_id"""

        if not self.lesson_id:
            return

        if not self._lesson:
            self._lesson = self.get_lesson(self.lesson_id)

        return self._lesson

    @lesson_cache.memoize(timeout=60)
    def get_all_participant(self) -> list[Participant, UserProject]:
        """Return all participants and their projects in the course"""

        return (
            self.db.query(Participant, UserProject)
            .filter(Participant.course_id == self.course_id)
            .join(
                UserProject,
                and_(
                    UserProject.participant_id == Participant.id,
                    UserProject.lesson_id == self.lesson_id,
                ),
                isouter=True,
            )
            .all()
        )


class LessonUserController(CourseUserController, LessonBaseController):
    def __init__(
        self,
        project: UserProject | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self._project = project

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

    @lesson_cache.memoize(timeout=300)
    def get_proj_by_ptc_id(self, ptc_id: int) -> UserProject:
        return (
            self.db.query(UserProject)
            .options(joinedload(UserProject.lesson))
            .filter(UserProject.lesson_id == self.lesson_id)
            .filter(UserProject.participant_id == ptc_id)
            .first()
        )

    @property
    def my_project(self) -> UserProject:
        """Return participant's UserProject"""

        if not self.my_participant:
            return

        if not self._project:
            self._project = self.get_proj_by_ptc_id(self.my_participant.id)

        return self._project

    async def update_ptc_status(self, active: bool):
        """Update Participant.active

        1. Change ``active``
        2. If status changed, send broadcast message
        """

        toggled = self.my_participant.active != active

        if toggled:
            self.my_participant.active = active
            self.db.add(self.my_participant)
            self.db.commit()

            data = serializer.participant(self.my_participant, self.my_project)
            room = Room.LESSON.format(course_id=self.course_id, lesson_id=self.lesson_id)

            await sio.emit(
                WSEvent.PARTICIPANT_STATUS,
                data=data,
                room=room,
                uuid=f"ptc-{self.my_participant.id}",
            )

            # Invalidate cache
            course_cache.delete_memoize(
                CourseUserController.get_ptc_by_user_id,
                self,  # alternative to CourseUserController object
                self.my_participant.user_id,
            )
            course_cache.delete_memoize(
                CourseUserController.get_ptc,
                self,  # alternative to CourseUserController object
                self.my_participant.id,
            )
