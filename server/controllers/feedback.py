from collections import defaultdict
from typing import Any

from sqlalchemy.orm import joinedload, contains_eager

from server.controllers.project import ProjectController, ProjectFileController
from server.models.course import PROJ_PERM, UserProject
from server.models.feedback import CodeReference, Feedback, FeedbackViewerMap, Comment
from server.utils.exceptions import ProjectNotFoundException
from server.utils.serializer import iso8601


class FeedbackController(ProjectController):
    def get_feedbacks_on_file(
        self,
        project_id: int,
        filename: str,
    ) -> list[tuple[CodeReference, Feedback, Comment]]:
        """Return code reference + feedback + comment rows"""
        return (
            self.db.query(CodeReference, Feedback, Comment)
            .filter(CodeReference.project_id == project_id)
            .filter(CodeReference.file == filename)
            .filter(CodeReference.deleted.is_(False))
            .join(Feedback, Feedback.code_ref_id == CodeReference.id)
            .join(Comment, Comment.feedback_id == Feedback.id, isouter=True)
            .all()
        )

    def get_all_feedbacks(self) -> list[dict[str, Any]]:
        """Return all feedback information on a lesson."""

        rows: list[UserProject] = (
            self.db.query(UserProject)
            # CodeReference
            .join(CodeReference, CodeReference.project_id == UserProject.id)
            .filter(CodeReference.deleted.is_(False))
            # Feedback
            .join(Feedback, Feedback.code_ref_id == CodeReference.id)
            # Must have a permission
            .join(FeedbackViewerMap, FeedbackViewerMap.feedback_id == Feedback.id)
            .filter(FeedbackViewerMap.participant_id == self.my_participant.id)
            # Outer join Comment
            .join(Comment, Comment.feedback_id == Feedback.id, isouter=True)
            .options(
                contains_eager(UserProject.code_references)
                .contains_eager(CodeReference.feedbacks)
                .contains_eager(Feedback.comments)
            )
            .all()
        )

        resp: list[dict[str, Any]] = []

        for project in rows:
            resp.append(self._build_dict(owner_id=project.participant_id, refs=project.code_references))

        return resp

    def get_feedbacks(self, owner_id: int | None, filename: str | None) -> dict:
        """Return all feedback information on specific file.

        Args:
            owner_id (int | None): owner user's participant ID
            filename (str | None): filename to which feedbacks are attached.
        """

        if not owner_id or not filename:
            return self.get_all_feedbacks()

        # Check readability to the file
        proj_file_ctrl = ProjectFileController(
            user_id=self.user_id, course_id=self.course_id, lesson_id=self.lesson_id, db=self.db
        )
        _, target_proj = proj_file_ctrl.get_target_info(target_ptc_id=owner_id, check_perm=PROJ_PERM.READ)

        # Query
        rows = (
            self.db.query(CodeReference)
            # CodeReference
            .filter(CodeReference.project_id == target_proj.id)
            .filter(CodeReference.file == filename)
            .filter(CodeReference.deleted.is_(False))
            # Feedback
            .join(Feedback, Feedback.code_ref_id == CodeReference.id)
            # Must have a permission
            .join(FeedbackViewerMap, FeedbackViewerMap.feedback_id == Feedback.id)
            .filter(FeedbackViewerMap.participant_id == self.my_participant.id)
            # outer join Comment
            .join(Comment, Comment.feedback_id == Feedback.id, isouter=True)
            .options(contains_eager(CodeReference.feedbacks).contains_eager(Feedback.comments))
            .all()
        )

        return self._build_dict(owner_id, rows)

    def _build_dict(self, owner_id: int, refs: list[CodeReference]) -> dict[str, Any]:
        """Build response dictionary"""
        # Query permission
        fb_ids = []
        for ref in refs:
            for fb in ref.feedbacks:
                fb_ids.append(fb.id)

        perms: list[FeedbackViewerMap] = (
            self.db.query(FeedbackViewerMap)
            .filter(FeedbackViewerMap.feedback_id.in_(fb_ids))
            .filter(FeedbackViewerMap.valid.is_(True))
            .all()
        )
        perm_dict = defaultdict(list)
        for perm in perms:
            perm_dict[perm.feedback_id].append(perm.participant_id)

        # Build response
        _refs = [
            dict(
                id=ref.id,
                line=ref.line,
                feedbacks=[
                    dict(
                        id=fb.id,
                        ptcId=fb.participant_id,
                        createdAt=iso8601(fb.created_at),
                        resolved=fb.resolved,
                        acl=perm_dict[fb.id],
                        comments=[
                            dict(
                                id=cmt.id,
                                ptcId=cmt.participant_id,
                                content=cmt.content,
                                createdAt=iso8601(cmt.created_at),
                                updatedAt=iso8601(cmt.updated_at),
                            )
                            for cmt in fb.comments
                        ],
                    )
                    for fb in ref.feedbacks
                ],
            )
            for ref in refs
        ]

        ref = refs[0] if refs else None
        return {
            "ownerId": owner_id,
            "projectId": ref.project_id if ref else None,
            "file": ref.file if ref else None,
            "refs": _refs,
        }
