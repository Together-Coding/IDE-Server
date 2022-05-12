from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from constants.redis import SIZE_LIMIT, RedisKey
from constants.s3 import S3Key
from server.controllers.base import LessonBaseController
from server.controllers.file import RedisControllerMixin, S3ControllerMixin
from server.controllers.template import LessonTemplateController
from server.helpers import s3
from server.helpers.redis_ import r
from server.models.course import PROJ_PERM, Participant, ProjectViewer, UserProject
from server.utils.etc import get_hashed
from server.utils.exceptions import (
    ForbiddenProjectException,
    ParticipantNotFoundException,
    ProjectFileException,
    ProjectNotFoundException,
)
from server.utils.time_utils import utc_dt_now
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

    def _check_permission(
        self, check_perm: PROJ_PERM, viewer: Participant, target_ptc: Participant, target_proj: UserProject
    ):
        perm: ProjectViewer = (
            self.db.query(ProjectViewer)
            .filter(ProjectViewer.viewer_id == viewer.id)  # 요청을 보낸 유저
            .filter(ProjectViewer.project_id == target_proj.id)  # R/W/X 대상 프로젝트
            .first()
        )

        allowed = False
        if viewer.is_teacher or target_ptc.is_teacher:
            # 선생으로부터 요청 or 선생의 코드 요청
            # 권한이 명시되어 있지 않거나 (기본), 명시적으로 허용된 경우에 OK
            if not perm or perm.has_perm(check_perm):
                allowed = True
        else:
            # 둘 다 선생이 아닌 경우, 권한이 존재한다면 OK
            if perm and perm.has_perm(check_perm):
                allowed = True

        return allowed

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
                s3_bulk_file_key=s3_key.KEY_BULK_FILE,
            )
            self.set_total_file_size(r_list_key, r_size_key=r_size_key)

        return r.zrange(redis_key.KEY_USER_FILE_LIST.format(ptc_id=self.my_participant.id), 0, -1)

    def _ptc_info(self, ptc_id: int) -> Participant:
        """Return ``ptc_id`` related ``Participant`` and its ``UserProject``"""

        target_ptc: Participant = (
            self.db.query(Participant).filter(Participant.id == ptc_id).options(joinedload(Participant.project)).first()
        )
        return target_ptc, target_ptc.project if target_ptc else None

    def get_target_info(
        self, target_ptc_id: int, check_perm: PROJ_PERM | None = None
    ) -> tuple[Participant, UserProject]:
        """Return ``Participant`` related with ``target_ptc_id`` and its ``UserProject``
        with additional exceptions and permission check.

        Args:
            target_ptc_id (int): target participant ID
            perm (PROJ_PERM | None, optional): permission to check if exists. Defaults to None.

        Raises:
            ParticipantNotFoundException: When the target does not exists
            ProjectNotFoundException: When the target did not enter the lesson
            ForbiddenProjectException: When no enough permission

        Returns:
            tuple[Participant, UserProject]: target user's
        """

        # 자기 자신에 대한 요청
        if target_ptc_id == self.my_participant.id:
            return self.my_participant, self.my_project

        target_ptc, target_proj = self._ptc_info(target_ptc_id)

        if not target_ptc:
            raise ParticipantNotFoundException("존재하지 않는 유저입니다.")
        elif not target_proj:
            raise ProjectNotFoundException("현재 강의에 참여하지 않은 유저입니다.")

        # 권한 확인
        if check_perm:
            allowed = self._check_permission(check_perm, self.my_participant, target_ptc, target_proj)
            if not allowed:
                raise ForbiddenProjectException("해당 유저에 대한 읽기 권한이 없습니다.")

        return target_ptc, target_proj

    def get_dir_info(self, target_ptc_id: int) -> list[str]:
        """Return target user's file list

        Args:
            target_ptc_id (int): participant ID that is the owner of the project
                                 the requester want to see.
        """

        # "My" file list is processed by ``get_my_file_list``
        if target_ptc_id == self.my_participant.id:
            return self.get_my_dir_info()

        self.get_target_info(target_ptc_id, PROJ_PERM.READ)

        # 대상 프로젝트를 읽을 수 있다면, 저장소에서 가져온다.
        r_files_key = RedisKey(self.course_id, self.lesson_id).KEY_USER_FILE_LIST.format(ptc_id=target_ptc_id)

        return r.zrange(r_files_key, 0, -1)

    def get_file_content(self, owner_id: int, filename: str):
        """Return file content from Redis.
        When the file is in S3, download it and store into Redis before returning it.

        Args:
            owner_id (int): owner ID of the file
            filename (str): filename to read
        """

        target_ptc, target_proj = self.get_target_info(owner_id, PROJ_PERM.READ)

        # File list 에 존재하는지 확인
        redis_key = RedisKey(self.course_id, self.lesson_id)
        _r_list_key = redis_key.KEY_USER_FILE_LIST.format(ptc_id=target_ptc.id)
        size = r.zscore(_r_list_key, filename)

        # Redis 에 없는 경우
        if size is None:
            # S3 에 유저별 코드 zip 파일이 존재하는지 확인. 없다면 에러 반환
            s3_key = S3Key(self.course_id, self.lesson_id)
            _user_project_key = s3_key.KEY_USER_PROJECT.format(ptc_id=target_ptc.id)
            if not s3.is_exists(_user_project_key):
                raise ProjectFileException("파일이 존재하지 않습니다.")

            # 있다면 압축을 풀고 Redis 에 저장. 해당 UserProject 가 active 상태라면 TTL=0,
            # inactive 상태라면 TTL=3600 을 설정하여, Redis 메모리를 불필요하게 차지하지 않도록 한다.
            _r_file_key_func = lambda hash: redis_key.KEY_USER_FILE_CONTENT.format(ptc_id=target_ptc.id, hash=hash)
            _r_size_key = redis_key.KEY_USER_CUR_SIZE.format(ptc_id=target_ptc.id)
            _s3_bulk_file_key = s3_key.KEY_BULK_FILE
            _ttl = None if target_proj.active else 3600
            self.extract_to_redis(
                _user_project_key, _r_list_key, _r_file_key_func, _s3_bulk_file_key, _r_size_key, _ttl, overwrite=False
            )

            # 사이즈 다시 확인
            size = r.zscore(_r_list_key, filename)

        # Redis 에서 반환
        _r_file_key = redis_key.KEY_USER_FILE_CONTENT.format(ptc_id=target_ptc.id, hash=get_hashed(filename))
        if size is None or size < 0:
            raise ProjectFileException("파일이 존재하지 않습니다.")
        elif 0 <= size < SIZE_LIMIT:  # 적당한 크기
            return r.get(_r_file_key)
        elif SIZE_LIMIT < size:  # Redis 임의 제한 초과
            # AWS S3 에서 bulk file 다운로드, 반환
            s3_object_key = r.get(_r_file_key)
            return self.get_s3_object_content(s3_object_key).decode()
