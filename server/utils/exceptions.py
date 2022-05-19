class BaseException(Exception):
    def __init__(self, error: str):
        self.error = error


class MissingFieldException(BaseException):
    pass

class AccessCourseFailException(BaseException):
    """Failed to access a course. The reasons are...
    - The course does not exist
    - The course is in non-accessible status
    - Not registered to the course
    etc
    """
    pass

class ProjectFileException(BaseException):
    pass


class ParticipantNotFoundException(BaseException):
    pass


class ProjectNotFoundException(BaseException):
    pass


class ForbiddenProjectException(BaseException):
    pass


class FileCRUDException(BaseException):
    pass


class FileAlreadyExistsException(FileCRUDException):
    pass


class TotalSizeExceededException(BaseException):
    """Total file size is greater than limit"""

    pass
