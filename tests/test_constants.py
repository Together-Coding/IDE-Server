from uuid import uuid4

from constants.redis import RedisKey
from constants.s3 import S3Key


def rand_str():
    return str(uuid4())


def test_redis_key():
    course_id = 123
    lesson_id = 456
    redis_key = RedisKey(course_id, lesson_id)

    assert redis_key.KEY_TEMPLATE_FILE_LIST == (RedisKey.PREFIX + RedisKey.KEY_TEMPLATE_FILE_LIST).format(
        course_id=course_id, lesson_id=lesson_id
    )

    name = rand_str()
    assert redis_key.KEY_TEMPLATE_FILE_CONTENT.format(hash=name) == (
        RedisKey.PREFIX + RedisKey.KEY_TEMPLATE_FILE_CONTENT
    ).format(course_id=course_id, lesson_id=lesson_id, hash=name)

    ptc_id = 99
    assert redis_key.KEY_USER_CUR_SIZE.format(ptc_id=ptc_id) == (RedisKey.PREFIX + RedisKey.KEY_USER_CUR_SIZE).format(
        course_id=course_id, lesson_id=lesson_id, ptc_id=ptc_id
    )

    ptc_id = 1
    assert redis_key.KEY_USER_PREV_CURSOR.format(ptc_id=ptc_id) == (
        RedisKey.PREFIX + RedisKey.KEY_USER_PREV_CURSOR
    ).format(course_id=course_id, lesson_id=lesson_id, ptc_id=ptc_id)

    ptc_id = 123
    assert redis_key.KEY_USER_FILE_LIST.format(ptc_id=ptc_id) == (RedisKey.PREFIX + RedisKey.KEY_USER_FILE_LIST).format(
        course_id=course_id, lesson_id=lesson_id, ptc_id=ptc_id
    )

    ptc_id = 19
    name = rand_str()
    assert redis_key.KEY_USER_FILE_CONTENT.format(ptc_id=ptc_id, hash=name) == (
        RedisKey.PREFIX + RedisKey.KEY_USER_FILE_CONTENT
    ).format(course_id=course_id, lesson_id=lesson_id, ptc_id=ptc_id, hash=name)


def test_s3_key():
    course_id = 123
    lesson_id = 456
    s3_key = S3Key(course_id, lesson_id)

    assert s3_key.KEY_LESSON_TEMPLATE == (S3Key.PREFIX + S3Key.KEY_LESSON_TEMPLATE).format(
        course_id=course_id, lesson_id=lesson_id
    )

    ptc_id = 99
    assert s3_key.KEY_USER_PROJECT.format(ptc_id=ptc_id) == (S3Key.PREFIX + S3Key.KEY_USER_PROJECT).format(
        course_id=course_id, lesson_id=lesson_id, ptc_id=ptc_id
    )

    filename = rand_str()
    assert s3_key.KEY_BULK_FILE.format(ptc_id=3, filename=filename) == (S3Key.PREFIX + S3Key.KEY_BULK_FILE).format(
        course_id=course_id, lesson_id=lesson_id, ptc_id=3, filename=filename
    )
