from server.controllers.lesson import LessonUserController


class CursorController(LessonUserController):
    def get_last_cursor(self, owner_id: int, file: str) -> str:
        """Return user's previous cursor on owner's file.

        Args:
            owner_id (int): owner user's participant ID
            file (str): filename

        Returns:
            str: cursor info if exists, otherwise, "0"
        """

        return self.redis_ctrl.get_last_cursor(self.my_participant.id, owner_id, file) or "0"

    def update_last_cursor(self, owner_id: int, file: str, cursor: str):
        """Update user's previous cursor on owner's file.

        Args:
            owner_id (int): owner user's participant ID
            file (str): filename
            cursor (str): cursor info
        """

        # Update only if the owner has the file
        if self.redis_ctrl.has_file(filename=file, ptc_id=owner_id, encoded=False):
            self.redis_ctrl.set_last_cursor(self.my_participant.id, owner_id, file, cursor)
