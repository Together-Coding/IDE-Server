from __future__ import annotations

import io
import os

from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from configs import settings
from constants.redis import SIZE_LIMIT
from constants.s3 import S3Key
from server.controllers.lesson import LessonBaseController, LessonUserController
from server.controllers.template import LessonTemplateController
from server.helpers import s3
from server.helpers.cache import ptc_cache, lesson_cache
from server.models.course import PROJ_PERM, Participant, ProjectViewer, UserProject
from server.models.feedback import CodeReference
from server.utils.etc import text_decode, text_encode
from server.utils.exceptions import (
    FileAlreadyExistsException,
    ForbiddenProjectException,
    ParticipantNotFoundException,
    ProjectFileException,
    ProjectNotFoundException,
    TotalSizeExceededException,
)
from server.utils.time_utils import utc_dt_now
from server.websockets import session as ws_session


class PingController(LessonUserController):
    async def update_recent_activity(self, target_ptc_id: int | None):
        if not target_ptc_id:
            target_ptc_id = self.my_participant.id

        if self.my_participant.id != target_ptc_id:
            # Accessing other ptc's project
            proj_file_ctrl = ProjectFileController(
                course_id=self.course_id,
                lesson_id=self.lesson_id,
                user_id=self.user_id,
                db=self.db,
            )

            # Check permission and raise exception if no perm or other cases
            proj_file_ctrl.get_target_info(target_ptc_id, PROJ_PERM.READ)

            target_user_id = self.get_ptc(target_ptc_id).user_id
        else:
            # Accessing my project
            target_user_id = self.user_id

        target_proj_ctrl = ProjectController(
            course_id=self.course_id,
            lesson_id=self.lesson_id,
            user_id=target_user_id,
            db=self.db,
        )

        if not target_proj_ctrl.my_project:
            target_proj_ctrl.create_if_not_exists()

        target_proj_ctrl.my_project.recent_activity_at = utc_dt_now()
        target_proj_ctrl.my_project.active = True
        self.db.add(target_proj_ctrl.my_project)

        # Update the participant's status
        await self.update_ptc_status(active=True)

        self.db.commit()


class ProjectController(LessonUserController):
    def create_if_not_exists(self) -> UserProject:
        """Create user's ``UserProject`` if not exists"""
        if not self.my_project:
            self._project = UserProject(lesson_id=self.lesson_id, participant_id=self.my_participant.id, active=True)
            self.db.add(self._project)
            self.db.flush()

            # 수업 템플릿 코드 적용
            tmpl_ctrl = LessonTemplateController(course_id=self.course_id, lesson_id=self.lesson_id, db=self.db)
            tmpl_ctrl.apply_to_user_project(self.my_participant, self.my_project.lesson)

            self.my_project.template_applied = True
            self.db.add(self.my_project)
            self.db.commit()

            lesson_cache.delete_memoize(LessonBaseController.get_all_participant, self)
            lesson_cache.delete_memoize(LessonUserController.get_proj_by_ptc_id, self, self.my_participant.id)
            lesson_cache.delete_memoize(ProjectFileController._ptc_info, self, self.my_participant.id)

        return self.my_project

    @lesson_cache.memoize(timeout=300)
    def _accessible_to(
        self,
        course_id: int,
        ptc_id: int,
        is_teacher: bool,
    ) -> list[tuple[Participant, UserProject, ProjectViewer]]:
        """Return user's accessible project owner list."""

        if is_teacher:
            # 선생인 경우, 전체 학생의 레코드 반환
            # ProjectViewer 에서 권한을 명시할 수 있으므로, 이 테이블을 join
            query = (
                self.db.query(Participant, UserProject, ProjectViewer)
                .filter(Participant.course_id == course_id)  # 자신이 속한 수업의 유저들
                .filter(Participant.id != ptc_id)  # 자신 제외
                .join(UserProject, UserProject.participant_id == Participant.id)  # 유저의 프로젝트
                .join(
                    ProjectViewer,
                    and_(
                        ProjectViewer.project_id == UserProject.id,
                        ProjectViewer.viewer_id == ptc_id,
                    ),
                    isouter=True,
                )  # 유저의 권한
            )
        else:
            # 학생인 경우, ``ProjectViewer.viewer`` 값이 자기 자신인 레코드를 이용
            query = (
                self.db.query(Participant, UserProject, ProjectViewer)
                .join(UserProject, UserProject.participant_id == Participant.id)  # 유저의 프로젝트
                .join(ProjectViewer, ProjectViewer.project_id == UserProject.id)  # 유저의 권한
                .filter(ProjectViewer.viewer_id == ptc_id)  # 자신이 볼 수 있는 프로젝트
            )

            # 학생인 경우, 항상 선생을 포함한다.
            teacher_query = (
                self.db.query(Participant, UserProject, ProjectViewer)
                .filter(Participant.course_id == course_id)
                .filter(Participant.role == Participant.KEY_TEACHER)
                .join(UserProject, UserProject.participant_id == Participant.id)
                .join(
                    ProjectViewer,
                    and_(
                        ProjectViewer.project_id == UserProject.id,
                        ProjectViewer.viewer_id == ptc_id,
                    ),
                    isouter=True,
                )
            )
            query = query.union(teacher_query)

        return query.all()

    def accessible_to(self) -> list[tuple[Participant, UserProject, ProjectViewer]]:
        return self._accessible_to(
            self.course_id,
            self.my_participant.id,
            self.my_participant.is_teacher,
        )

    @lesson_cache.memoize(timeout=300)
    def _accessed_by(
        self,
        course_id: int,
        ptc_id: int,
        project_id: int | None,
        is_teacher: bool,
    ) -> list[Participant, UserProject, ProjectViewer]:
        """Return user list who can access my project"""

        if not project_id:
            return []

        if is_teacher:
            # 선생인 경우, 전체 학생의 레코드 반환.
            # ProjectViewer 에서 권한을 명시할 수 있으므로, 이 테이블을 join
            query = (
                self.db.query(Participant, UserProject, ProjectViewer)
                .filter(Participant.course_id == course_id)
                .filter(Participant.id != ptc_id)
                .join(UserProject, UserProject.participant_id == Participant.id)
                .join(
                    ProjectViewer,
                    and_(
                        ProjectViewer.viewer_id == Participant.id,
                        ProjectViewer.project_id == project_id,
                    ),
                    isouter=True,
                )
            )
        else:
            # 학생인 경우, ``ProjectViewer.project_id`` 값이 자신의 프로젝트인 레코드 이용
            query = (
                self.db.query(Participant, UserProject, ProjectViewer)
                .join(UserProject, UserProject.participant_id == Participant.id)
                .join(ProjectViewer, ProjectViewer.viewer_id == Participant.id)
                .filter(ProjectViewer.project_id == project_id)  # 자신의 프로젝트의 viewer
            )

            # 학생인 경우, 항상 선생을 포함한다.
            teacher_query = (
                self.db.query(Participant, UserProject, ProjectViewer)
                .filter(Participant.course_id == course_id)
                .filter(Participant.role == Participant.KEY_TEACHER)
                .join(UserProject, UserProject.participant_id == Participant.id)
                .join(
                    ProjectViewer,
                    and_(
                        ProjectViewer.viewer_id == Participant.id,
                        ProjectViewer.project_id == project_id,
                    ),
                    isouter=True,
                )
            )
            query = query.union(teacher_query)

        return query.all()

    def accessed_by(self) -> list[Participant, UserProject, ProjectViewer]:
        return self._accessed_by(
            self.course_id,
            self.my_participant.id,
            self.my_project.id if self.my_project else None,
            self.my_participant.is_teacher,
        )

    def modify_project_permission(self, target_id: int, permission: int) -> None | ProjectViewer:
        """Create/Modify user's ProjectViewer record.

        Args:
            target_id (int): 권한을 수정할 상대 유저 ID
            permission (int): READ: 4, WRITE: 2, EXEC: 1
        """

        # 자신에 대한 권한은 추가하지 않음
        if target_id == self.my_participant.id:
            return

        permission = int(permission) & PROJ_PERM.ALL

        row: ProjectViewer | None = (
            self.db.query(ProjectViewer)
            .filter(ProjectViewer.project_id == self.my_project.id)
            .filter(ProjectViewer.viewer_id == target_id)
            .first()
        )

        # 권한 변화가 없는 경우
        if row and row.permission == permission:
            return None

        try:
            if not row:
                row = ProjectViewer(project_id=self.my_project.id, viewer_id=target_id, permission=0)
        except IntegrityError:  # No foreign key
            return

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

        # Invalidate cache related to the accessibility from the target user to me
        lesson_cache.delete_memoize(
            ProjectController._accessed_by,
            self,
            self.course_id,
            self.my_participant.id,
            self.my_project.id,
            self.my_participant.is_teacher,
        )

        # Invalidate cache related to the accessibility of the target user
        target_ptc = self.get_ptc(target_id)
        lesson_cache.delete_memoize(
            ProjectController._accessible_to,
            self,
            self.course_id,
            target_id,
            target_ptc.is_teacher,
        )

        lesson_cache.delete_memoize(
            ProjectFileController._check_permission,
            self,  # alternative to ProjectFileController object
            PROJ_PERM.ALL,  # ignored
            target_ptc,
            self.my_participant,
            self.my_project,
        )

        return row


class ProjectFileController(LessonUserController):
    def _get_project_cached(self, target_ptc: Participant):
        """Return user's cached project files from Redis"""

        return self.redis_ctrl.get_file_list(ptc_id=target_ptc.id, check_content=True)

    @lesson_cache.memoize(timeout=60, ignore_args=["check_perm"])
    def _check_permission(
        self,
        check_perm: PROJ_PERM,
        viewer: Participant,
        target_ptc: Participant,
        target_proj: UserProject,
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

    @lesson_cache.memoize(timeout=60)
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
            raise ProjectNotFoundException("아직 강의에 참여하지 않은 유저입니다.")

        # 권한 확인
        if check_perm:
            allowed = self._check_permission(check_perm, self.my_participant, target_ptc, target_proj)
            if not allowed:
                raise ForbiddenProjectException(f"해당 유저에 대한 {PROJ_PERM.translate(check_perm)} 권한이 없습니다.")

        return target_ptc, target_proj

    def get_dir_info(self, target_ptc_id: int) -> list[str]:
        """Return target user's file list (encoded)

        Args:
            target_ptc_id (int): participant ID that is the owner of the project
                                 the requester want to see.
        """

        target_ptc, target_proj = self.get_target_info(target_ptc_id, PROJ_PERM.READ)
        self_request = target_ptc.id == self.my_participant.id

        # UserProject 생성이 안 된 경우
        if not target_proj:
            # 자기 자신에 대한 요청인 경우, 생성
            if self_request:
                proj_ctrl = ProjectController(
                    user_id=self.user_id,
                    course_id=self.course_id,
                    lesson_id=self.lesson_id,
                    participant=target_ptc,
                    project=target_proj,
                    db=self.db,
                )
                target_proj = proj_ctrl.create_if_not_exists()
            else:  # 다른 유저의 생성되지 않은 프로젝트: get_target_info 에서 이미 처리됨
                raise ProjectNotFoundException("아직 강의에 참여하지 않은 유저입니다.")
        else:  # UserProject 가 있는 경우
            # Redis 에 캐시되어 있는지 확인
            project_files = self._get_project_cached(target_ptc)

            if project_files:
                return project_files

            # 캐시 되어있지 않다면, S3 에서 유저의 프로젝트 다운로드
            self.s3_ctrl.extract_to_redis(ptc_id=target_ptc.id)
            self.redis_ctrl.set_total_file_size(target_ptc.id)

        # 대상 프로젝트를 읽을 수 있다면, 저장소에서 가져온다.
        return self.redis_ctrl.get_file_list(ptc_id=target_ptc.id, check_content=True)

    def get_file_content(self, owner_id: int, filename: str):
        """Return file content from Redis.
        When the file is in S3, download it and store into Redis before returning it.

        Args:
            owner_id (int): owner ID of the file
            filename (str): filename to read
        """

        enc_filename = text_encode(filename)
        target_ptc, target_proj = self.get_target_info(owner_id, PROJ_PERM.READ)

        # File list 에 존재하는지 확인
        size = self.redis_ctrl.get_file_size_score(enc_filename, ptc_id=target_ptc.id, encoded=True)

        # Redis 에 없는 경우
        if size is None:
            # S3 에 유저별 코드 zip 파일이 존재하는지 확인. 없다면 에러 반환
            s3_key = S3Key(self.course_id, self.lesson_id)
            _user_project_key = s3_key.KEY_USER_PROJECT.format(ptc_id=target_ptc.id)
            if not s3.is_exists(_user_project_key):
                raise ProjectFileException("파일이 존재하지 않습니다.")

            # 있다면 압축을 풀고 Redis 에 저장. 해당 UserProject 가 active 상태라면 TTL=0,
            # ~inactive 상태라면 TTL=3600 을 설정하여, Redis 메모리를 불필요하게 차지하지 않도록 한다.~
            #  -> 다른 유저가 수정하는 경우 activity ping 을 보내므로, S3 uploader (bg worker) 에게 맡기면 된다.
            ttl = None  # if target_proj.active else 3600
            self.s3_ctrl.extract_to_redis(ptc_id=target_ptc.id, ttl=ttl, overwrite=False)

            # 사이즈 다시 확인
            size = self.redis_ctrl.get_file_size_score(enc_filename, ptc_id=target_ptc.id, encoded=True)

        # Redis 에서 반환
        if size is None or size < 0:
            raise ProjectFileException("파일이 존재하지 않습니다.")
        elif 0 <= size < SIZE_LIMIT:  # 적당한 크기
            return self.redis_ctrl.get_file(filename=enc_filename, ptc_id=target_ptc.id, hashed=False)
        elif SIZE_LIMIT < size:  # Redis 임의 제한 초과
            # AWS S3 에서 bulk file 다운로드, 반환
            s3_object_key = self.redis_ctrl.get_file(filename=enc_filename, ptc_id=target_ptc.id, hashed=False)
            return self.s3_ctrl.get_s3_object_content(s3_object_key).decode()

    def create_file_or_dir(self, owner_id: int, type_: str, name: str):
        """Create file or directory at the owner's project.

        Args:
            owner_id (int): owner ID of the new file/directory
            type_ (str): "file" or "directory"
            name (str): name of the file/directory
        """

        target_ptc, _ = self.get_target_info(owner_id, PROJ_PERM.READ | PROJ_PERM.WRITE)

        if type_ == "directory":
            filename = os.path.join(name, self.redis_ctrl.redis_key.DUMMY_DIR_MARK)
            content = self.redis_ctrl.redis_key.DUMMY_DIR_MARK_CONTENT

        if type_ == "file":
            filename = name
            content = self.redis_ctrl.redis_key.NEW_FILE_CONTENT

        try:
            self.redis_ctrl.create_file(
                filename=filename,
                content=content,
                ptc_id=target_ptc.id,
                mark_directory=True,
            )
        except FileAlreadyExistsException as e:
            if type_ == "directory":
                e.error = "이미 존재하는 폴더입니다."
            raise e

    def get_related_code_ref(self, project_id: int, type_: str, name: str) -> list[CodeReference]:
        query = (
            self.db.query(CodeReference)
            .filter(CodeReference.project_id == project_id)
            .filter(CodeReference.deleted.is_(False))
        )

        if type_ == "directory":
            return query.filter(CodeReference.file.like(f"{name}/%")).all()  # Use `like` clause for directory
        else:
            return query.filter(CodeReference.file == name).all()

    def update_file_or_dir_name(self, owner_id: int, type_: str, name: str, rename: str):
        """Update name of file or directory at the owner's project.

        Args:
            owner_id (int): owner ID of the file/directory
            name (str): file or directory name to change
            rename (str): changed name
        """

        # 권한 확인
        _, target_proj = self.get_target_info(owner_id, PROJ_PERM.READ | PROJ_PERM.WRITE)

        code_refs = self.get_related_code_ref(target_proj.id, type_, name)

        if type_ == "directory":
            # 디렉터리 내부 파일명 모두 변경
            if not self.redis_ctrl.has_directory(dirname=name, ptc_id=owner_id):
                raise FileAlreadyExistsException("존재하지 않는 폴더입니다.")

            if self.redis_ctrl.has_directory(dirname=rename, ptc_id=owner_id):
                raise FileAlreadyExistsException("같은 이름의 폴더가 이미 존재합니다.")

            enc_filenames = self.redis_ctrl.get_file_list(ptc_id=owner_id, check_content=False)
            for enc_filename in enc_filenames:
                filename = text_decode(enc_filename)
                if filename.startswith(name):
                    new_filename = filename.replace(name, rename, 1)
                    self.redis_ctrl.rename_file(filename=filename, new_filename=new_filename, ptc_id=owner_id)

            # code_references 참조 위치 변경
            for code_ref in code_refs:
                code_ref.file = code_ref.file.replace(name, rename, 1)
                self.db.add(code_ref)

        else:
            # 해당 파일명 변경
            if not self.redis_ctrl.has_file(filename=name, ptc_id=owner_id, encoded=False):
                raise FileAlreadyExistsException("존재하지 않는 파일입니다.")

            if self.redis_ctrl.has_file(filename=rename, ptc_id=owner_id, encoded=False):
                raise FileAlreadyExistsException("같은 이름의 파일이 이미 존재합니다.")

            self.redis_ctrl.rename_file(filename=name, new_filename=rename, ptc_id=owner_id)
            self.redis_ctrl.mark_as_directory(filename=rename, ptc_id=owner_id)

            # code_references 참조 위치 변경
            for code_ref in code_refs:
                code_ref.file = rename
                self.db.add(code_ref)

        self.db.commit()

    def delete_file_or_dir(self, owner_id: int, type_: str, name: str):
        """Delete file or directory

        Args:
            owner_id (int): owner user's participant ID
            type_ (str): "file" or "directory"
            name (str): file or directory name to delete
        """

        # 권한 확인
        _, target_proj = self.get_target_info(owner_id, PROJ_PERM.READ | PROJ_PERM.WRITE)

        if type_ == "directory":
            # 해당 디렉터리 내부 파일 모두 삭제
            if not self.redis_ctrl.has_directory(dirname=name, ptc_id=owner_id):
                raise FileAlreadyExistsException("존재하지 않는 폴더입니다.")

            enc_filenames = self.redis_ctrl.get_file_list(ptc_id=owner_id, check_content=False)
            for enc_filename in enc_filenames:
                filename = text_decode(enc_filename)
                if filename.startswith(name):
                    self.redis_ctrl.delete_file(filename=enc_filename, ptc_id=owner_id, encoded=True)

        else:  # file
            # 해당 파일 삭제
            if not self.redis_ctrl.has_file(filename=name, ptc_id=owner_id, encoded=False):
                raise FileAlreadyExistsException("존재하지 않는 파일입니다.")

            enc_filename = text_encode(name)

            # If bulk file, make sure to delete it from S3
            size = self.redis_ctrl.get_file_size_score(filename=name, ptc_id=owner_id, encoded=False)
            if size > SIZE_LIMIT:
                object_key = self.redis_ctrl.get_file(filename=enc_filename, ptc_id=owner_id, hashed=False)
                self.s3_ctrl.delete_s3_object(object_key=object_key)

            # Delete file key
            self.redis_ctrl.delete_file(filename=enc_filename, ptc_id=owner_id, encoded=True)

        # code_references 참조 수정
        code_refs = self.get_related_code_ref(target_proj.id, type_, name)
        for code_ref in code_refs:
            code_ref.deleted = True
            self.db.add(code_ref)

        self.db.commit()

    def file_save(self, owner_id: int, file: str, content: str):
        """Save file content into Redis

        Args:
            owner_id (int): file owner's participant ID
            file (str): filename
            content (str): entire file content to save
        """

        enc_filename = text_encode(file)

        # Check READ and WRITE permission. If denied, ForbiddenProjectException is raised.
        self.get_target_info(target_ptc_id=owner_id, check_perm=PROJ_PERM.READ & PROJ_PERM.WRITE)

        # If the file not in the file list, append it.
        if not self.redis_ctrl.has_file(filename=enc_filename, ptc_id=owner_id, encoded=True):
            self.redis_ctrl.append_file_list(filename=enc_filename, size=0, ptc_id=owner_id, encoded=True)

        # Retrieve current file size
        prev_file_size = self.redis_ctrl.get_file_size_score(filename=enc_filename, ptc_id=owner_id, encoded=True)
        new_file_size = len(content)

        prev_total_size = self.redis_ctrl.get_total_file_size(ptc_id=owner_id)
        new_total_size = prev_total_size + new_file_size - prev_file_size

        # If total size is greater than limit, respond an error
        if new_total_size > settings.PROJECT_SIZE_LIMIT:
            raise TotalSizeExceededException(
                f"수정 내역을 저장할 수 없습니다. 프로젝트의 크기 제한({settings.PROJECT_SIZE_LIMIT//2**20}MB)을 초과하였습니다."
            )

        # Save content
        if new_file_size > SIZE_LIMIT:
            object_key = self.s3_ctrl.s3_key.KEY_BULK_FILE.format(ptc_id=owner_id, filename=enc_filename)

            # Save content in S3
            self.s3_ctrl.put_s3_object(object_key, io.StringIO(content))

            # Save S3 object key in Redis
            self.redis_ctrl.store_file(filename=enc_filename, content=object_key, ptc_id=owner_id, hashed=False)
        else:  # size is less than limit
            # Save content in Redis
            self.redis_ctrl.store_file(filename=enc_filename, content=content, ptc_id=owner_id, hashed=False)

        # Update file size
        self.redis_ctrl.set_file_size(filename=enc_filename, size=new_file_size, ptc_id=owner_id, encoded=True)
        self.redis_ctrl.increase_total_file_size(amount=new_file_size - prev_file_size, ptc_id=owner_id)
