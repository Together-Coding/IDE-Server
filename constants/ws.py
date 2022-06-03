class WSEvent:
    # Admin and Monitoring
    WS_MONITOR = "WS_MONITOR"
    WS_MONITOR_EVENT = "WS_MONITOR_EVENT"  # Monitored event (message)
    TIMESTAMP_ACK = "TIMESTAMP_ACK"
    TIME_SYNC = "TIME_SYNC"
    TIME_SYNC_ACK = "TIME_SYNC_ACK"

    # Common
    ERROR = "ERROR"

    # Subscription
    SUBS_PARTICIPANT = "SUBS_PARTICIPANT"
    UNSUBS_PARTICIPANT = "UNSUBS_PARTICIPANT"
    SUBS_PARTICIPANT_LIST = "SUBS_PARTICIPANT_LIST"

    # Lesson
    INIT_LESSON = "INIT_LESSON"
    ALL_PARTICIPANT = "ALL_PARTICIPANT"

    # Project
    ACTIVITY_PING = "ACTIVITY_PING"
    PARTICIPANT_STATUS = "PARTICIPANT_STATUS"

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

    # Feedback
    FEEDBACK_LIST = "FEEDBACK_LIST"
    FEEDBACK_ADD = "FEEDBACK_ADD"
    FEEDBACK_MOD = "FEEDBACK_MOD"
    FEEDBACK_COMMENT = "FEEDBACK_COMMENT"
    FEEDBACK_COMMENT_MOD = "FEEDBACK_COMMENT_MOD"


WS_MONITOR_EVENTS = [
    WSEvent.WS_MONITOR,
    WSEvent.WS_MONITOR_EVENT,
    WSEvent.TIMESTAMP_ACK,
    # WSEvent.TIME_SYNC,
    # WSEvent.TIME_SYNC_ACK,
]

ROOM_TYPE = "room-{type}"  # session key to store room names to remember what rooms the user enterred.


class Room:
    WS_MONITOR = "admin:monitor:{course_id}:{lesson_id}"

    PERSONAL_PTC = "{course_id}:{lesson_id}:{ptc_id}:self"  # Used to retrieve session id from participant id
    SUBS_PTC = "{course_id}:{lesson_id}:{ptc_id}"  # Used to subscribe specific participant
    LESSON = "{course_id}:{lesson_id}"
