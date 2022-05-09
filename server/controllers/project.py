from __future__ import annotations

from sqlalchemy.orm import Session

from server.controllers.base import LessonBaseController
from server.models.course import Participant, ProjectViewer, UserProject
from server.utils.time_utils import utc_dt_now
from server.websockets import session as ws_session


class PingController(LessonBaseController):
    def update_recent_activity(self):
        if not self.my_project:
            return

        self.my_project.recent_activity_at = utc_dt_now()
        self.my_project.active = True
        self.db.commit()


class ProjectController(LessonBaseController):
    @classmethod
    async def from_session(cls, sid: str, db: Session) -> ProjectController:
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

        return ProjectController(user_id=user_id, course_id=course_id, lesson_id=lesson_id, db=db)

    def accessible_to(self) -> list[tuple[Participant, UserProject, ProjectViewer]]:
        """Return user's accessible project owner list."""

        if self.my_participant.is_teacher:
            # 선생인 경우, 전체 학생의 레코드 반환
            # ProjectViewer 에서 권한을 명시할 수 있으므로, 이 테이블을 join
            query = (
                self.db.query(Participant, UserProject, ProjectViewer)
                .filter(Participant.course_id == self.course_id)  # 자신이 속한 수업의 유저들
                .filter(Participant.user_id != self.user_id)  # 자신 제외
                .join(UserProject, UserProject.participant_id == Participant.id)  # 유저의 프로젝트
                .join(ProjectViewer, ProjectViewer.viewer_id == Participant.id, isouter=True)  # 유저의 권한
            )
        else:
            # 학생인 경우, ``ProjectViewer.viewer`` 값이 자기 자신인 레코드를 이용
            query = (
                self.db.query(Participant, UserProject, ProjectViewer)
                .join(UserProject, UserProject.participant_id == Participant.id)  # 유저의 프로젝트
                .join(ProjectViewer, ProjectViewer.project_id == UserProject.id)  # 유저의 권한
                .filter(ProjectViewer.viewer_id == self.my_participant.id)  # 자신이 볼 수 있는 프로젝트
            )

            # 학생인 경우, 항상 선생을 포함한다.
            teacher_query = (
                self.db.query(Participant, UserProject, ProjectViewer)
                .filter(Participant.course_id == self.course_id)
                .filter(Participant.role == Participant.KEY_TEACHER)
                .join(UserProject, UserProject.participant_id == Participant.id)
                .join(ProjectViewer, ProjectViewer.project_id == UserProject.id, isouter=True)
                .filter(ProjectViewer.viewer_id == self.my_participant.id)
            )
            query = query.union(teacher_query)

        return query.all()

    def accessed_by(self):
        """Return user list who can access my project"""

        if self.my_participant.is_teacher:
            # 선생인 경우, 전체 학생의 레코드 반환.
            # ProjectViewer 에서 권한을 명시할 수 있으므로, 이 테이블을 join
            query = (
                self.db.query(Participant, UserProject, ProjectViewer)
                .filter(Participant.course_id == self.course_id)
                .filter(Participant.user_id != self.user_id)
                .join(UserProject, UserProject.participant_id == Participant.id)
                .join(ProjectViewer, ProjectViewer.viewer_id == Participant.id, isouter=True)
            )
        else:
            # 학생인 경우, ``ProjectViewer.project_id`` 값이 자신의 프로젝트인 레코드 이용
            query = (
                self.db.query(Participant, UserProject, ProjectViewer)
                .join(UserProject, UserProject.participant_id == Participant.id)
                .join(ProjectViewer, ProjectViewer.viewer_id == Participant.id)
                .filter(ProjectViewer.project_id == self.my_project.id)  # 자신의 프로젝트의 viewer
            )

            # 학생인 경우, 항상 선생을 포함한다.
            teacher_query = (
                self.db.query(Participant, UserProject, ProjectViewer)
                .filter(Participant.course_id == self.course_id)
                .filter(Participant.role == Participant.KEY_TEACHER)
                .join(UserProject, UserProject.participant_id == Participant.id)
                .join(ProjectViewer, ProjectViewer.viewer_id == Participant.id, isouter=True)
                .filter(ProjectViewer.project_id == self.my_project.id)
            )
            query = query.union(teacher_query)

        return query.all()


if __name__ == "__main__":
    from server.helpers.db import SessionLocal

    pc = ProjectController(user_id=15, course_id=22, lesson_id=2, db=SessionLocal())
    participant = pc.my_participant
    print("ME: ", participant)

    print("my accessible users")
    partcs = pc.accessible_to()
    for p in partcs:
        print(p)

    print("accessible to mine")
    my_p = pc.my_project
    print(my_p)
    partcs = pc.accessed_by()
    for p in partcs:
        print(p)
