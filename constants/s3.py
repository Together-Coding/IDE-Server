from constants.base import LessonKeyBase


class S3Key(LessonKeyBase):
    PREFIX = "/course/{course_id}/{lesson_id}"

    # 수업 템플릿 ZIP 파일
    KEY_LESSON_TEMPLATE = "/template.zip"

    # 유저별 프로젝트 ZIP 파일
    KEY_USER_PROJECT = "/project/{ptc_id}.zip"

    # 용량 제한을 넘는 템플릿 or 유저 파일
    KEY_BULK_FILE = "/bulk/{filename}"  # filename: hashed content
