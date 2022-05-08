from server.controllers.base import LessonBaseController
from server.controllers.course import CourseController
from server.models.course import Participant, ProjectViewer, UserProject
from server.utils.time_utils import utc_dt_now


class PingController(LessonBaseController):
    def update_recent_activity(self):
        if not self.my_project:
            return

        self.my_project.recent_activity_at = utc_dt_now()
        self.my_project.active = True
        self.db.commit()
