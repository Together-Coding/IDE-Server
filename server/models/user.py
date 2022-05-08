from sqlalchemy import DATETIME, TEXT, Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from server.helpers.db import Base
from server.utils.time_utils import utc_dt_now


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(60), nullable=False)
    name = Column(String(20), nullable=False)
    password = Column(String(80), nullable=False)
    from_social = Column(Boolean, nullable=False)
    created_at = Column(DATETIME, nullable=False, default=utc_dt_now)

    feeds = relationship("Feed", foreign_keys="Feed.user_id")
    participation = relationship("Participant", foreign_keys="Participant.user_id")

class Feed(Base):
    __tablename__ = "feeds"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    from_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    type = Column(String(60), nullable=False, default="")
    data = Column(TEXT, nullable=True)
    created_at = Column(DATETIME, nullable=False, default=utc_dt_now)

    user = relationship("User", back_populates="feeds", foreign_keys=[user_id])
