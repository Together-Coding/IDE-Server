from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from constants.redis import RedisKey
from constants.s3 import S3Key
from server.helpers.redis_ import r
from server.controllers.base import LessonBaseController
from server.controllers.template import LessonTemplateController
from server.controllers.file import RedisControllerMixin, S3ControllerMixin
from server.models.course import PROJ_PERM, Participant, ProjectViewer, UserProject
from server.utils.exceptions import ParticipantNotFoundException, ProjectNotFoundException
from server.utils.time_utils import utc_dt_now
from server.utils.etc import get_hashed
from server.websockets import project
from server.websockets import session as ws_session


class PingController(LessonBaseController):
    def update_recent_activity(self):
        if not self.my_project:
            return

        self.my_project.recent_activity_at = utc_dt_now()
        self.my_project.active = True
        self.db.commit()


class ProjectController(LessonBaseController):
    def create_if_not_exists(self) -> UserProject:
        """Create user's ``UserProject`` if not exists"""
        if not self.my_project:
            self._project = UserProject(lesson_id=self.lesson_id, participant_id=self.my_participant.id, active=True)
            self.db.add(self._project)
            self.db.commit()

        return self.my_project

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

    def modify_project_permission(self, user_id: int, permission: int) -> None | ProjectViewer:
        """Create/Modify users's ProjectViewer record.

        Args:
            user_id (int): 권한을 수정할 상대 유저 ID
            permission (int): READ: 4, WRITE: 2, EXEC: 1
        """

        permission = int(permission) & PROJ_PERM.ALL

        row = (
            self.db.query(ProjectViewer)
            .filter(ProjectViewer.project_id == self.my_project.id)
            .filter(ProjectViewer.viewer_id == user_id)
            .first()
        )

        # 권한 변화가 없는 경우
        if row and row.permission == permission:
            return None

        if not row:
            row = ProjectViewer(project_id=self.my_project.id, viewer_id=user_id, permission=0)

        # 권한 변경, 저장
        diff_perm = row.permission ^ permission  # 1 on different bit
        row.permission = permission
        self.db.add(row)
        self.db.commit()

        # 변경된 권한을 계산
        added = 0
        removed = 0
        # if READ flag is changed
        if diff_perm & PROJ_PERM.READ:
            # if the changed flag is in the current permission
            if row.permission & PROJ_PERM.READ:
                added += PROJ_PERM.READ
            else:
                removed += PROJ_PERM.READ
        if diff_perm & PROJ_PERM.WRITE:
            if row.permission & PROJ_PERM.WRITE:
                added += PROJ_PERM.WRITE
            else:
                removed += PROJ_PERM.WRITE
        if diff_perm & PROJ_PERM.EXEC:
            if row.permission & PROJ_PERM.EXEC:
                added += PROJ_PERM.EXEC
            else:
                removed += PROJ_PERM.EXEC

        row.added = added
        row.removed = removed
        return row


class ProjectFileController(LessonBaseController, S3ControllerMixin, RedisControllerMixin):
    def _get_project_cached(self):
        """Return user's cached project files from Redis"""

        redis_key = RedisKey(self.course_id, self.lesson_id)

        return self.get_cached_files(
            r_list_key=redis_key.KEY_USER_FILE_LIST.format(ptc_id=self.my_participant.id),
            r_file_key_func=lambda hash: redis_key.KEY_USER_FILE_CONTENT.format(
                ptc_id=self.my_participant.id, hash=hash
            ),
            check_content=True,
        )

    def get_my_dir_info(self) -> list[str]:
        """Return file list of my project

        If ``UserProject`` does not exists for the user, create new one, and apply template project to it.
        If exists but not cached by Redis, download zip from S3 and save the contents into Redis.

        Returns:
            list[str]: file names of the user
        """

        redis_key = RedisKey(self.course_id, self.lesson_id)
        s3_key = S3Key(self.course_id, self.lesson_id)

        # UserProject 생성이 안 된 경우 (수업에 처음 입장한 시점)
        if not self.my_project:
            # UserProject 생성
            proj_ctrl = ProjectController(
                self.user_id, self.course_id, self.lesson_id, self.my_participant, self.my_project, db=self.db
            )
            proj_ctrl.create_if_not_exists()

            # 수업 템플릿 코드 적용
            tmpl_ctrl = LessonTemplateController(self.db)
            tmpl_ctrl.apply_to_user_project(self.my_participant, self.my_lesson)
        else:  # UserProject 가 있는 경우
            # Redis 에 캐시되어 있는지 확인
            project_files = self._get_project_cached()

            if project_files:
                return project_files

            # 캐시 되어있지 않다면, S3 에서 유저의 프로젝트 다운로드
            r_list_key = redis_key.KEY_USER_FILE_LIST.format(ptc_id=self.my_participant.id)
            r_size_key = redis_key.KEY_USER_CUR_SIZE.format(ptc_id=self.my_participant.id)

            self.extract_to_redis(
                object_key=s3_key.KEY_USER_PROJECT.format(ptc_id=self.my_participant.id),
                r_list_key=r_list_key,
                r_file_key_func=lambda hash: redis_key.KEY_USER_FILE_CONTENT.format(
                    ptc_id=self.my_participant.id, hash=hash
                ),
                s3_bulk_file_key=s3_key.KEY_BULK_FILE
            )
            self.set_total_file_size(r_list_key, r_size_key=r_size_key)

        return r.zrange(redis_key.KEY_USER_FILE_LIST.format(ptc_id=self.my_participant.id), 0, -1)

    def get_dir_info(self, target_ptc_id: int) -> list[str]:
        """Return target user's file list

        Args:
            target_ptc_id (int): participant ID that is the owner of the project
                                 the requester want to see.
        """

        # "My" file list is processed by ``get_my_file_list``
        if target_ptc_id == self.my_participant.id:
            return self.get_my_dir_info()
        else:
            target_ptc: Participant = (
                self.db.query(Participant)
                .filter(Participant.id == target_ptc_id)
                .options(joinedload(Participant.project))
                .first()
            )
            target_proj = target_ptc.project if target_ptc else None

        if not target_ptc:
            raise ParticipantNotFoundException("존재하지 않는 유저입니다.")
        elif not target_proj:
            raise ProjectNotFoundException("현재 강의에 참여하지 않은 유저입니다.")

        # 권한 확인
        perm: ProjectViewer = (
            self.db.query(ProjectViewer)
            .filter(ProjectViewer.project_id == target_proj.id)  # 해당 유저의 프로젝트
            .filter(ProjectViewer.viewer_id == self.my_participant.id)
            .first()
        )

        allowed = False
        if self.my_participant.is_teacher or target_ptc.is_teacher:
            # 선생으로부터 요청 or 선생의 코드 요청
            # 권한이 명시되어 있지 않거나 (기본), 명시적으로 읽기가 허용된 경우에 OK
            if not perm or perm.read_allowed:
                allowed = True
        else:
            # 둘 다 선생이 아닌 경우, 읽기 권한이 존재한다면 OK
            if perm and perm.read_allowed:
                allowed = True

        if not allowed:
            raise ParticipantNotFoundException("해당 유저에 대한 읽기 권한이 없습니다.")

        # 대상 프로젝트를 읽을 수 있다면, 저장소에서 가져온다.
        r_files_key = RedisKey(self.course_id, self.lesson_id).KEY_USER_FILE_LIST.format(ptc_id=target_ptc_id)

        return r.zrange(r_files_key, 0, -1)
