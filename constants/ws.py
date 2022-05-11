class WSEvent:
    INIT_LESSON = "INIT_LESSON"
    ACTIVITY_PING = "ACTIVITY_PING"
    PROJECT_ACCESSIBLE = "PROJECT_ACCESSIBLE"
    PROJECT_PERM = "PROJECT_PERM"
    DIR_INFO = "DIR_INFO"


class Room:
    PERSONAL_PTC = "ptc-{ptc_id}"
    LESSON = "{course_id}:{lesson_id}"
