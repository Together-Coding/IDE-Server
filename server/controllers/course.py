from server.controllers.base import BaseController
from server.models.course import Course, Participant
from server.utils.exceptions import AccessCourseFailException
from server.helpers.cache import course_cache


class CourseBaseController(BaseController):
    def __init__(
        self,
        course_id: int,
        course: Course | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.course_id = course_id

        self._course = course

    @property
    def my_course(self) -> Course:
        if not self._course:
            self._course = self.db.query(Course).filter(Course.id == self.course_id).first()

        return self._course


class CourseUserController(CourseBaseController):
    def __init__(
        self,
        user_id: int,
        participant: Participant | None = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        self.user_id = user_id

        self._participant = participant

    @course_cache.memoize(timeout=300)
    def get_ptc(self, ptc_id: int) -> Participant:
        return self.db.query(Participant).filter(Participant.id == ptc_id).first()

    @course_cache.memoize(timeout=300)
    def get_ptc_by_user_id(self, user_id: int) -> Participant:
        return (
            self.db.query(Participant)
            .filter(Participant.course_id == self.course_id)
            .filter(Participant.user_id == user_id)
            .first()
        )

    @property
    def my_participant(self) -> Participant:
        if not self._participant:
            self._participant = self.get_ptc_by_user_id(self.user_id)

        return self._participant

    def check_accessibility(self):
        """Check accessibility from the user to the course.
        If not accessible, ``AccessCourseFailException`` is raised."""

        if not self.my_course:
            raise AccessCourseFailException("존재하지 않는 수업입니다.")

        if not self.my_participant:
            raise AccessCourseFailException("수업 참여자가 아닙니다.")

        # 선생인 경우, 통과
        if self.my_participant.role == Participant.KEY_TEACHER:
            return

        # if not self.my_course.accessible:
        # raise AccessCourseFailException("수업이 접근 불가능 상태로 설정되어 있습니다. 수업 담당자에게 문의 바랍니다.")
