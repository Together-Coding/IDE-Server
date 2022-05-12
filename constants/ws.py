class WSEvent:
    # Initial and common
    INIT_LESSON = "INIT_LESSON"
    ACTIVITY_PING = "ACTIVITY_PING"

    # Project permission
    PROJECT_ACCESSIBLE = "PROJECT_ACCESSIBLE"
    PROJECT_PERM = "PROJECT_PERM"

    # File and directory
    DIR_INFO = "DIR_INFO"
    FILE_OPEN = "FILE_OPEN"


class Room:
    PERSONAL_PTC = "ptc-{ptc_id}"
    LESSON = "{course_id}:{lesson_id}"
