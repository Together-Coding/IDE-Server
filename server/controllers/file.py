import os
import tempfile
import zipfile
from typing import Callable

from botocore.errorfactory import ClientError

from constants.redis import SIZE_LIMIT, RedisKey
from constants.s3 import S3Key
from server.helpers import s3, sentry
from server.helpers.redis_ import r
from server.utils.etc import get_hashed, text_encode
from server.utils.exceptions import FileAlreadyExistsException, ProjectFileException


class RedisController:
    def __init__(
        self,
        course_id: int,
        lesson_id: int,
    ):
        self.redis_key = None

        self.update_base_key(course_id, lesson_id)

    def update_base_key(
        self,
        course_id: int,
        lesson_id: int,
    ):
        self.redis_key = RedisKey(course_id, lesson_id)

    def store_file(
        self,
        filename: str,
        content: str | int,
        ptc_id: int | None = None,
        hashed=False,
    ):
        """Store file content into Redis

        Args:
            filename (str): filename to store as key
            content (str | int): content to store as value
            ptc_id (int | None, optional): owner participant's ID. Defaults to None.
            hashed (bool, optional): whether the filename is hashed or encoded. Defaults to False.
        """

        if not hashed:
            filename = get_hashed(filename)

        if ptc_id:
            file_key = self.redis_key.KEY_USER_FILE_CONTENT.format(ptc_id=ptc_id, hash=filename)
        else:
            file_key = self.redis_key.KEY_TEMPLATE_FILE_CONTENT.format(hash=filename)

        r.set(file_key, content)

    def get_file(
        self,
        filename: str,
        ptc_id: int | None = None,
        hashed=False,
    ) -> str:
        """Return file content from Redis.

        Args:
            filename (str): filename to read
            ptc_id (int | None, optional): owner participant ID. Defaults to None.
            hashed (bool, optional): whether the filename is hashed or encoded. Defaults to False.
        """

        if not hashed:
            filename = get_hashed(filename)

        if ptc_id:
            file_key = self.redis_key.KEY_USER_FILE_CONTENT.format(ptc_id=ptc_id, hash=filename)
        else:
            file_key = self.redis_key.KEY_TEMPLATE_FILE_CONTENT.format(hash=filename)

        return r.get(file_key)

    def get_file_size_len(
        self,
        filename: str,
        ptc_id: int | None = None,
        hashed=False,
    ) -> int:
        """Return strlen of the filename.
        Unlike ``get_file_size_score``, this uses `Redis.strlen` method.

        Args:
            filename (str): target filename
            ptc_id (int | None, optional): owner's participant ID. Defaults to None.
            hashed (bool, optional): whether filename is encoded or hashed + encoded. Defaults to False.
        """

        if not hashed:
            filename = get_hashed(filename)

        if ptc_id:
            file_key = self.redis_key.KEY_USER_FILE_CONTENT.format(ptc_id=ptc_id, hash=filename)
        else:
            file_key = self.redis_key.KEY_TEMPLATE_FILE_CONTENT.format(hash=filename)

        return r.strlen(file_key) or 0

    def get_file_size_score(
        self,
        filename: str,
        ptc_id: int | None = None,
        encoded=False,
    ) -> int | float:
        """Return score of ``list_key:filename``.

        Args:
            filename (str): target filename
            ptc_id (int | None, Optional): owner's participant ID. Defaults to None
            encoded (bool, optional): whether filename is encoded or plaintext. Defaults to False.
        """

        if ptc_id:
            list_key = self.redis_key.KEY_USER_FILE_LIST.format(ptc_id=ptc_id)
        else:
            list_key = self.redis_key.KEY_TEMPLATE_FILE_LIST

        # If filename is raw plain text, encode it
        if not encoded:
            filename = text_encode(filename)

        return r.zscore(list_key, filename)

    def has_file(self, **kwargs):
        """Return True if file exists in file list, otherwise, False."""
        size = self.get_file_size_score(**kwargs)

        return False if size is None else True

    def increase_total_file_size(
        self,
        amount: int,
        ptc_id: int,
    ) -> int:
        """Increase total file size by amount

        Args:
            amount (int): increase amount. It can be negative.
            ptc_id (int): target participant ID
        """

        key = self.redis_key.KEY_USER_CUR_SIZE.format(ptc_id=ptc_id)
        return r.incrby(key, amount)

    def set_total_file_size(
        self,
        ptc_id: int,
    ) -> int:
        """Set total size bytes to ``size_key`` in Redis.
        Total size equals to the sum of the scores of ``list_key`` items.

        Args:
            ptc_id (int): owner of the files

        XXX: If you want to calculate total size by iterating all file contents,
             please make sure files that are in AWS S3 is considered too.
        """

        list_key = self.redis_key.KEY_USER_FILE_LIST.format(ptc_id=ptc_id)
        size_key = self.redis_key.KEY_USER_CUR_SIZE.format(ptc_id=ptc_id)

        total = 0
        for _, size in r.zscan_iter(list_key, score_cast_func=int):
            total += size

        r.set(size_key, total)
        return total

    def append_file_list(
        self,
        filename: str,
        size: int,
        ptc_id: int | None = None,
        encoded=False,
    ):
        """Add new filename into file list. If ``ptc_id`` is None, it is appended to template list.

        Args:
            filename (str): filename to add
            size (int): file size
            ptc_id (int | None, optional): owner participant's ID. Defaults to None.
            encoded (bool, optional): whether the filename is encoded or plaintext. Defaults to False.
        """

        if not encoded:
            filename = text_encode(filename)

        if ptc_id:
            list_key = self.redis_key.KEY_USER_FILE_LIST.format(ptc_id=ptc_id)
        else:
            list_key = self.redis_key.KEY_TEMPLATE_FILE_LIST

        r.zadd(list_key, {filename: size})

    def get_file_list(
        self,
        ptc_id: int | None = None,
        check_content: bool = True,
    ) -> list[str]:
        """Return cached files from Redis.
        If ``check_content`` is True, this checks whether each file in the list is stored in the Redis.

        Args:
            ptc_id (int): owner participant's ID
            check_content (bool, optional): should check existence of each file. Defaults to True.

        Returns:
            list[str]: file names that cached
        """

        if ptc_id:
            list_key = self.redis_key.KEY_USER_FILE_LIST.format(ptc_id=ptc_id)
            file_key_func = lambda hash: self.redis_key.KEY_USER_FILE_CONTENT.format(ptc_id=ptc_id, hash=hash)
        else:
            list_key = self.redis_key.KEY_TEMPLATE_FILE_LIST
            file_key_func = lambda hash: self.redis_key.KEY_TEMPLATE_FILE_CONTENT.format(hash=hash)

        data = r.zscan_iter(list_key, score_cast_func=int)
        enc_file_names = [filename for filename, _ in data]  # remove score values

        if not check_content:
            return enc_file_names

        cached = bool(enc_file_names)
        if cached:
            # Eviction 되는 경우의 처리를 위해, 파일들이 모두 존재하는지 확인
            for enc_filename in enc_file_names:
                # Although empty string can't be stored in Redis, check content length.
                _hashed_name = get_hashed(enc_filename)
                _size = r.strlen(file_key_func(_hashed_name))
                if _size <= 0:
                    cached = False
                    break

        return enc_file_names if cached else []

    def create_file(
        self,
        filename: str,
        content: str,
        ptc_id: int,
    ):
        """Create new file
        1. Append new filename into file list
        2. Add file content

        Args:
            filename (str): filename to create
            content (str): file content
            ptc_id (int): owner participant's ID
        """

        enc_filename = text_encode(filename)

        if self.has_file(filename=enc_filename, ptc_id=ptc_id, encoded=True):
            raise FileAlreadyExistsException("이미 존재하는 파일입니다.")

        self.append_file_list(filename=enc_filename, size=len(content), ptc_id=ptc_id, encoded=True)
        self.store_file(filename=enc_filename, content=content, ptc_id=ptc_id, hashed=False)


class S3Controller:
    def __init__(
        self,
        course_id: int,
        lesson_id: int,
        redis_key: RedisKey,
    ):
        self.s3_key = S3Key(course_id, lesson_id)
        self.redis_key = redis_key

    @staticmethod
    def get_s3_object_content(
        object_key: str,
        bucket: str | None = None,
    ) -> bytes:
        obj = s3.get_object(object_key, bucket)
        return obj["Body"].read()

    def extract_to_redis(
        self,
        object_key: str | None = None,
        ptc_id: int | None = None,
        ttl: int | None = None,
        overwrite: bool = True,
    ):
        """Extract zip file from redis, and then store it into Redis

        1. Download zipped template file from AWS S3
        2. Extract it
        3. Read all extracted files and save data to Redis
            When a file size is more than limit, save the file to S3, and then
            store S3 object key in Redis instead of file content.
        ※ 파일 개수 혹은 용량 등에 대한 문제들은 업로드 시점에 처리해 줘야 함

        Args:
            ptc_id (int | None, optional): _description_. Defaults to None.
            ttl (int | None, optional): Time-to-live. Defaults to None.
            overwrite (bool, optional): If the key already exists, do/don't overwrite. Defaults to True.

        Raises:
            LessonTemplateException: When S3 object is not exists
            LessonTemplateException: When extraction failed
        """

        if ptc_id:
            object_key = object_key or self.s3_key.KEY_USER_PROJECT.format(ptc_id=ptc_id)
            r_list_key = self.redis_key.KEY_USER_FILE_LIST.format(ptc_id=ptc_id)
            r_file_key_func = lambda hash: self.redis_key.KEY_USER_FILE_CONTENT.format(ptc_id=ptc_id, hash=hash)
            r_size_key = self.redis_key.KEY_USER_CUR_SIZE.format(ptc_id=ptc_id)
        else:
            r_list_key = self.redis_key.KEY_TEMPLATE_FILE_LIST
            r_file_key_func = lambda hash: self.redis_key.KEY_TEMPLATE_FILE_CONTENT.format(hash=hash)
            r_size_key = None

        # S3 에서 다운로드 후 Redis 에 저장
        try:
            zip_file = s3.get_object(object_key)
        except ClientError:
            sentry.exc()
            raise ProjectFileException("프로젝트가 존재하지 않습니다.")

        with tempfile.TemporaryDirectory() as tmp_dir:  # str
            tmp_zip_fd, tmp_zip_path = tempfile.mkstemp(dir=tmp_dir)
            os.write(tmp_zip_fd, zip_file["Body"].read())
            os.fsync(tmp_zip_fd)  # Flush

            # 압축 해제
            try:
                unzip_dir = os.path.join(tmp_dir, "unzip")
                os.mkdir(unzip_dir)
                with zipfile.ZipFile(tmp_zip_path, "r") as zip_ref:
                    zip_ref.extractall(unzip_dir)
            except ValueError:  # extraction failed
                sentry.exc()
                raise ProjectFileException("프로젝트를 사용할 수 없습니다.")

            # 임시 파일들을 모두 읽고, 각각 Redis 에 저장
            for root, _, files in os.walk(unzip_dir):
                # /tmp/asdf/project_root/file.py -> project_root/file.py
                project_path = root.replace(unzip_dir, "").strip("/")  # Path from Project root

                for unzipped_file in files:
                    unzipped_file_path = os.path.join(root, unzipped_file)  # Absolute path
                    project_file_path = os.path.join(project_path, unzipped_file)  # file path from project root
                    enc_project_file_path = text_encode(project_file_path)
                    hashed_name = get_hashed(enc_project_file_path)
                    _r_file_key = r_file_key_func(hashed_name)

                    # 파일 리스트 저장
                    size = os.stat(unzipped_file_path).st_size
                    r.zadd(r_list_key, {enc_project_file_path: size})

                    # 기존 파일 사이즈 확인
                    if r_size_key:
                        old_size = r.strlen(_r_file_key) or 0

                    # 파일 저장
                    with open(unzipped_file_path, "rb") as fp:
                        content: bytes = fp.read()

                        # If no content, add one space to store it in Redis
                        if size <= 0:
                            content = b" "

                        if size <= SIZE_LIMIT:
                            r.set(name=_r_file_key, value=content, ex=ttl, nx=not overwrite)
                        else:
                            # 파일이 너무 큰 경우, S3 에 해당 파일 업로드
                            _hashed_content = get_hashed(content.decode())
                            _bulk_file_key = self.s3_key.KEY_BULK_FILE.format(filename=_hashed_content)

                            if not s3.is_exists(_bulk_file_key):
                                # S3 에 없는 경우, 해당 파일만 따로 업로드
                                s3.put_object(fp, _bulk_file_key)

                            # Redis 에 object path 저장
                            r.set(name=_r_file_key, value=_bulk_file_key, ex=ttl)

                    # 총 파일 사이즈 업데이트
                    if r_size_key:
                        r.incrby(r_size_key, size - old_size)

            # Set TTL
            if ttl:
                r.expire(r_list_key, ttl)
