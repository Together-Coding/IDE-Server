from constants.base import LessonKeyBase

SIZE_LIMIT = 134_217_728  # bytes == 128 MB


class RedisKey(LessonKeyBase):
    """
    Some keys are encoded by `server.utils.etc.text_encode`,
    and some of them are also hashed by `server.utils.etc.get_hashed` after encoded.
    """

    PREFIX = "crs:{course_id}:{lesson_id}:"

    # 템플릿 파일명 리스트
    KEY_TEMPLATE_FILE_LIST = "template:files"  # ZSET: enc(filename): size
    # 템플릿 파일 내용
    KEY_TEMPLATE_FILE_CONTENT = "template:files:{hash}"  # STRING(binary): hash(enc(filename)): content

    # 유저별 총 파일 사이즈
    KEY_USER_CUR_SIZE = "{ptc_id}:size"  # STRING (number)
    # 유저별 이전 커서 위치
    KEY_USER_PREV_CURSOR = "{ptc_id}:csr:last"  # HASH: target_user_id.filename: cursor_info

    # 유저별 파일명 리스트
    KEY_USER_FILE_LIST = "{ptc_id}:files"  # ZSET: enc(filename): size
    # 유저별 파일 내용
    KEY_USER_FILE_CONTENT = "{ptc_id}:files:{hash}"  # STRING(binary): hash(enc(filename)): content

    DUMMY_DIR_MARK = "_"  # Dummy file to keep track of empty directory
    DUMMY_DIR_MARK_CONTENT = " "  # Dummy content for dummy file
    NEW_FILE_CONTENT = " "  # Prevent error from being raised due to setting empty string.
