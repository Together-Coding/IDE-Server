from __future__ import annotations
from sqlalchemy import DATETIME, TEXT, Boolean, Column, ForeignKey, Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import relationship

from server.helpers.db import Base
from server.utils.time_utils import utc_dt_now


class CodeReference(Base):
    __tablename__ = "code_references"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("user_projects.id"), nullable=False)
    file = Column(TEXT, nullable=True)
    line = Column(String(255), nullable=True)
    deleted = Column(Boolean, nullable=False, default=False)

    project = relationship("UserProject", back_populates="code_references", uselist=False)
    feedbacks: list[Feedback] = relationship("Feedback")


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    code_ref_id = Column(Integer, ForeignKey("code_references.id"), nullable=False)
    participant_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    resolved = Column(Boolean, nullable=False, default=False)
    created_at = Column(DATETIME, nullable=False, default=utc_dt_now)

    code_reference: CodeReference = relationship("CodeReference", back_populates="feedbacks", uselist=False)
    viewer_map: list[FeedbackViewerMap] = relationship("FeedbackViewerMap")
    comments: list[Comment] = relationship("Comment")
    participant = relationship("Participant", uselist=False)


class FeedbackViewerMap(Base):
    __tablename__ = "feedback_viewer_map"
    __table_args__ = (PrimaryKeyConstraint("feedback_id", "participant_id"),)

    feedback_id = Column(Integer, ForeignKey("feedbacks.id"), nullable=False)
    participant_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    valid = Column(Boolean, nullable=False, default=True)

    feedback: Feedback = relationship("Feedback", back_populates="viewer_map", uselist=False)


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    feedback_id = Column(Integer, ForeignKey("feedbacks.id"), nullable=False)
    participant_id = Column(Integer, ForeignKey("participants.id"), nullable=False)
    content = Column(TEXT, nullable=False, default="")
    deleted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DATETIME, nullable=False, default=utc_dt_now)
    updated_at = Column(DATETIME, nullable=False, default=utc_dt_now, onupdate=utc_dt_now)

    feedback: Feedback = relationship("Feedback", back_populates="comments", uselist=False)
    participant = relationship("Participant", uselist=False)
    