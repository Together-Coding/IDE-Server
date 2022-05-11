from constants.base import LessonKeyBase

SIZE_LIMIT = 134_217_728  # bytes == 128 MB


class RedisKey(LessonKeyBase):
    PREFIX = "crs:{course_id}:{lesson_id}:"

    # 템플릿 파일명 리스트
    KEY_TEMPLATE_FILE_LIST = "template:files"  # ZSET: filename: size
    # 템플릿 파일 내용
    KEY_TEMPLATE_FILE_CONTENT = "template:files:{hash}"  # STRING(binary)

    # 유저별 총 파일 사이즈
    KEY_USER_CUR_SIZE = "{ptc_id}:size"  # STRING (number)
    # 유저별 이전 커서 위치
    KEY_USER_PREV_CURSOR = "{ptc_id}:csr:last"  # HASH: target_user_id.filename: cursor_info

    # 유저별 파일명 리스트
    KEY_USER_FILE_LIST = "{ptc_id}:files"  # ZSET: filename: size
    # 유저별 파일 내용
    KEY_USER_FILE_CONTENT = "{ptc_id}:files:{hash}"  # STRING(binary)


if __name__ == "__main__":
    rk = RedisKey(1, 2)
    print(rk.KEY_USER_CUR_SIZE)
    print(rk.KEY_USER_CUR_SIZE.format(ptc_id=1234))
