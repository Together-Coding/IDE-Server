from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from configs import settings

engine = create_engine(settings.SQLALCHEMY_DATABASE_URL, echo=settings.DB_ECHO)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class DefaultBase(object):
    def __repr__(self):
        try:
            return f'{type(self).__name__} id={getattr(self, "id")}'
        except AttributeError:
            return f'{type(self).__name__}'


Base = declarative_base(cls=DefaultBase)


def get_db_dep():
    """Dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db() -> Session:
    return next(get_db_dep())