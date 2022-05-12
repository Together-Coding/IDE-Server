import os
import tempfile
import zipfile
from typing import Callable

from botocore.errorfactory import ClientError

from constants.redis import SIZE_LIMIT
from server.helpers import s3, sentry
from server.helpers.redis_ import r
from server.utils.etc import get_hashed
from server.utils.exceptions import ProjectFileException


class RedisControllerMixin:
    @staticmethod
    def set_total_file_size(r_list_key: str, r_size_key: str):
        """Set total size bytes to ``r_size_key`` in Redis.
        Total size equals to the sum of the scores of ``r_list_key`` items.

        Args:
            r_list_key (str): file list key
            r_size_key (str): total size key

        XXX: If you want to calculate total size by iterating all file contents,
             please make sure files that are in AWS S3 is considered too.
        """

        data = r.zscan_iter(r_list_key, score_cast_func=int)

        total = 0
        for _, size in data:
            total += size

        r.set(r_size_key, total)
        return total

    @staticmethod
    def get_cached_files(r_list_key: str, r_file_key_func: Callable, check_content: bool = True) -> list[str]:
        """Return cached files from Redis if the files in the list
        are all in the Redis.

        Args:
            list_key (str): fie list key in Redis
            r_file_key_func (Callable): getter for file content key in Redis
            check_content (bool, optional): should check existence of each file. Defaults to True.

        Returns:
            list[str]: file names that cached
        """

        data = r.zscan_iter(r_list_key, score_cast_func=int)
        enc_file_names = [filename for filename, _ in data]  # remove score values

        if not check_content:
            return enc_file_names

        cached = False
        if enc_file_names:
            cached = True

            # Eviction 되는 경우의 처리를 위해, 파일들이 모두 존재하는지 확인
            for enc_filename in enc_file_names:
                # Although empty string can't be stored in Redis, check content length.
                _hashed_name = get_hashed(enc_filename)
                _size = r.strlen(r_file_key_func(_hashed_name))
                if _size <= 0:
                    cached = False
                    break

        return enc_file_names if cached else []


class S3ControllerMixin:
    @staticmethod
    def get_s3_object_content(object_key: str, bucket: str | None = None) -> bytes:
        obj = s3.get_object(object_key, bucket)
        return obj["Body"].read()

    @staticmethod
    def extract_to_redis(
        object_key: str,
        r_list_key: str,
        r_file_key_func: Callable,
        s3_bulk_file_key: str,
        r_size_key: str | None = None,
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
            object_key (str): S3 object key
            r_list_key (str): file list key in Redis
            r_file_key_func (Callable): getter for file content key in Redis
            s3_bulk_file_key (str): S3 object key for bulk file
            r_size_key (str | None): total score(size) of r_list_key items
            ttl (int | None): Time-to-live

        Raises:
            LessonTemplateException: When S3 object is not exists
            LessonTemplateException: When extraction failed
        """

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
                    project_file_path = os.path.join(project_path, unzipped_file)  # path from project root
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
                            _bulk_file_key = s3_bulk_file_key.format(filename=_hashed_content)

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
