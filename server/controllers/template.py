import os

from server.controllers.lesson import LessonBaseController
from server.models.course import Lesson, Participant
from server.utils.etc import get_hashed


class LessonTemplateController(LessonBaseController):
    """A controller that is used to manipulate template files attached to each lesson"""

    def _cache_template(self, lesson: Lesson):
        """Cache template files into Redis."""

        self.s3_ctrl.extract_to_redis(object_key=lesson.file.url, ttl=6 * 3600)

    def apply_to_user_project(self, ptc: Participant, lesson: Lesson):
        """Apply lesson template to user's project.

        Args:
            ptc (Participant): user's Participant
            lesson (Lesson): related Lesson
        """

        # 템플릿이 존재하지 않는 경우, 아무것도 하지 않는다.
        if not lesson.file or not lesson.file.url:
            return

        # Redis 에서 템플릿 정보 가져오기
        enc_filenames = self.redis_ctrl.get_file_list(check_content=True)

        # Redis 에 정보가 존재하지 않는 경우, S3 에서 다운로드 & 저장
        if not enc_filenames:
            self._cache_template(lesson)
            enc_filenames = self.redis_ctrl.get_file_list(check_content=False)

        # Redis 에 존재하는 템플릿 데이터들을 유저의 project 에 복사
        for enc_filename in enc_filenames:
            # XXX: Race condition 발생 가능
            _hashed_name = get_hashed(enc_filename)

            content = self.redis_ctrl.get_file(filename=_hashed_name, hashed=True)
            size = self.redis_ctrl.get_file_size_len(filename=_hashed_name, ptc_id=None, hashed=True)

            # 이미 동일한 파일명이 존재하는 경우, suffix 추가
            _name, _ext = os.path.splitext(enc_filename)
            dup_idx = 0
            while dup_idx < 100:  # Set max retry
                if self.redis_ctrl.has_file(filename=enc_filename, ptc_id=ptc.id, encoded=False):
                    enc_filename = f"{_name}_{dup_idx}.{_ext}"
                    dup_idx += 1
                else:
                    break
            else:
                # Do not overwrite existing file.
                continue

            # filename 을 새로 계산한 경우, hashed_name 재계산
            if dup_idx != 0:
                _hashed_name = get_hashed(enc_filename)

            # 파일명 리스트에 추가
            self.redis_ctrl.append_file_list(filename=enc_filename, size=size, ptc_id=ptc.id, encoded=True)

            # 기존 파일 사이즈 확인
            old_size = self.redis_ctrl.get_file_size_len(filename=_hashed_name, ptc_id=ptc.id, hashed=True)

            # 파일 내용 저장
            self.redis_ctrl.store_file(filename=_hashed_name, content=content, ptc_id=ptc.id, hashed=True)

            # 총 파일 사이즈 업데이트
            self.redis_ctrl.increase_total_file_size(amount=size - old_size, ptc_id=ptc.id)
