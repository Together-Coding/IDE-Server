from sqlalchemy.orm import Session


class BaseController:
    def __init__(self, db: Session | None = None, *args, **kwargs):
        self.db = db
