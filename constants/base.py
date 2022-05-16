from typing import Any


class KeyBase:
    PREFIX = ""

    def __getattribute__(self, name: str) -> Any:
        value = super().__getattribute__(name)

        if name.startswith("KEY_"):
            return self.PREFIX + value
        return value


class LessonKeyBase(KeyBase):
    def __init__(self, course_id: int, lesson_id: int):
        self.PREFIX = self.PREFIX.format(course_id=course_id, lesson_id=lesson_id)
