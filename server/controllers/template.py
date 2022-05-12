import os

from constants.redis import RedisKey
from constants.s3 import S3Key
from server.controllers.base import BaseContoller
from server.controllers.file import S3ControllerMixin, RedisControllerMixin
from server.helpers.redis_ import r
from server.models.course import Lesson, LessonFile, Participant
from server.helpers import s3
from server.utils.etc import get_hashed


class LessonTemplateController(BaseContoller, S3ControllerMixin, RedisControllerMixin):
    """A controller that is used to manipulate template files attached to each lesson"""

    def _cache_template(self, ptc: Participant, lesson: Lesson):
        """Cache template files into Redis."""

        redis_key = RedisKey(course_id=ptc.course_id, lesson_id=lesson.id)
        s3_key = S3Key(course_id=ptc.course_id, lesson_id=lesson.id)

        self.extract_to_redis(
            object_key=lesson.file.url,
            r_list_key=redis_key.KEY_TEMPLATE_FILE_LIST,
            r_file_key_func=lambda hash: redis_key.KEY_TEMPLATE_FILE_CONTENT.format(hash=hash),
            s3_bulk_file_key=s3_key.KEY_BULK_FILE,
            ttl=6 * 3600,
        )

    def _get_template_cached(self, redis_key: RedisKey, check_content: bool = True) -> list[str]:
        """Return cached template files from Redis if all template files are there

        Args:
            redis_key (RedisKey): RedisKey to generate `KEY_TEMPLATE_FILE_LIST`
            check_content (bool): If true, return file list from Redis right away

        Returns:
            list[str]: template file list if cached, otherwise, empty list
        """

        return self.get_cached_files(
            r_list_key=redis_key.KEY_TEMPLATE_FILE_LIST,
            r_file_key_func=lambda hash: redis_key.KEY_TEMPLATE_FILE_CONTENT.format(hash=hash),
            check_content=check_content,
        )

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
        redis_key = RedisKey(course_id=ptc.course_id, lesson_id=lesson.id)
        tmpl_files = list(self._get_template_cached(redis_key))

        # Redis 에 정보가 존재하지 않는 경우, S3 에서 다운로드 & 저장
        if not tmpl_files:
            self._cache_template(ptc, lesson)
            tmpl_files = self._get_template_cached(redis_key, check_content=False)

        # Redis 에 존재하는 템플릿 데이터들을 유저의 project 에 복사
        for filename in tmpl_files:
            # XXX: Race condition 발생 가능
            _hashed_name = get_hashed(filename)
            _tmpl_file_key = redis_key.KEY_TEMPLATE_FILE_CONTENT.format(hash=_hashed_name)

            content = r.get(_tmpl_file_key)
            size = r.strlen(_tmpl_file_key)

            # 이미 동일한 파일명이 존재하는 경우, suffix 추가
            idx = 0
            while bool(r.zscore(redis_key.KEY_USER_FILE_LIST, filename)):
                _name, _ext = os.path.splitext(filename)
                filename = f"{_name}_{idx}.{_ext}"

            # filename 을 새로 계산한 경우, hashed_name 재계산
            if idx != 0:
                _hashed_name = get_hashed(filename)

            # 파일명 리스트
            r.zadd(redis_key.KEY_USER_FILE_LIST.format(ptc_id=ptc.id), {filename: size})

            _redis_file_key = redis_key.KEY_USER_FILE_CONTENT.format(ptc_id=ptc.id, hash=_hashed_name)

            # 기존 파일 사이즈 확인
            old_size = r.strlen(_redis_file_key) or 0

            # 파일 내용 저장
            r.set(_redis_file_key, content)

            # 총 파일 사이즈 업데이트
            r.incrby(redis_key.KEY_USER_CUR_SIZE.format(ptc_id=ptc.id), size - old_size)
