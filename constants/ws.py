class WSEvent:
    # Common
    ERROR = "ERROR"

    # Lesson
    INIT_LESSON = "INIT_LESSON"
    ALL_PARTICIPANT = "ALL_PARTICIPANT"

    # Project
    ACTIVITY_PING = "ACTIVITY_PING"

    PROJECT_ACCESSIBLE = "PROJECT_ACCESSIBLE"
    PROJECT_PERM = "PROJECT_PERM"
    PROJECT_PERM_CHANGED = "PROJECT_PERM_CHANGED"

    # File and directory
    DIR_INFO = "DIR_INFO"
    FILE_READ = "FILE_READ"
    FILE_CREATE = "FILE_CREATE"
    FILE_UPDATE = "FILE_UPDATE"
    FILE_DELETE = "FILE_DELETE"

    # Cursor
    CURSOR_LAST = "CURSOR_LAST"
    CURSOR_MOVE = "CURSOR_MOVE"

    # File
    FILE_MOD = "FILE_MOD"
    FILE_SAVE = "FILE_SAVE"


class Room:
    PERSONAL_PTC = "ptc-{ptc_id}"  # Used to retrieve session id from participant id
    LESSON = "{course_id}:{lesson_id}"
