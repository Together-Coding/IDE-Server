from sqlalchemy.orm import Session

from server.models.course import Participant, UserProject


class BaseContoller:
    def __init__(self, db: Session | None = None):
        self.db = db


class CourseBaseController(BaseContoller):
    def __init__(self, user_id: int, course_id: int, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.user_id = user_id
        self.course_id = course_id


class LessonBaseController(CourseBaseController):
    def __init__(
        self,
        user_id: int,
        course_id: int,
        lesson_id: int,
        participant: Participant | None = None,
        project: UserProject | None = None,
        *args,
        **kwargs
    ):
        super().__init__(user_id, course_id, *args, **kwargs)

        self.lesson_id = lesson_id
        self._participant = participant
        self._project = project

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
