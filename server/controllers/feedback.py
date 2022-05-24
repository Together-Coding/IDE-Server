from collections import defaultdict
from typing import Any

from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import contains_eager, joinedload

from server.controllers.project import ProjectController, ProjectFileController
from server.models.course import PROJ_PERM, Participant, UserProject
from server.models.feedback import CodeReference, Comment, Feedback, FeedbackViewerMap
from server.utils.exceptions import FeedbackNotAuthException, FeedbackNotFoundException
from server.utils import serializer
from server.utils.serializer import iso8601, participant


class FeedbackController(ProjectController):
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
            .join(Comment, and_(Comment.feedback_id == Feedback.id, Comment.deleted.is_(False)), isouter=True)
            .options(joinedload(UserProject.participant))
            .options(
                contains_eager(UserProject.code_references)
                .contains_eager(CodeReference.feedbacks)
                .contains_eager(Feedback.comments)
                .contains_eager(Comment.participant)
            )
            .all()
        )

        resp: list[dict[str, Any]] = []

        for project in rows:
            resp.append(self._build_dict(owner=project.participant, project=project, refs=project.code_references))

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
        target_ptc, target_proj = proj_file_ctrl.get_target_info(target_ptc_id=owner_id, check_perm=PROJ_PERM.READ)

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
            .join(Comment, and_(Comment.feedback_id == Feedback.id, Comment.deleted.is_(False)), isouter=True)
            .options(
                contains_eager(CodeReference.feedbacks)
                .contains_eager(Feedback.comments)
                .joinedload(Comment.participant)
            )
            .all()
        )

        return self._build_dict(target_ptc, target_proj, rows)

    def _build_dict(self, owner: Participant, project: UserProject, refs: list[CodeReference]) -> dict[str, Any]:
        """Build response dictionary"""

        result = {
            "ownerId": owner.id,
            "ownerNickname": owner.nickname,
            "projectId": project.id,
        }

        if not refs:
            result["refs"] = []
            return result

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
        _refs = []
        for ref in refs:
            _feedbacks = []
            for fb in ref.feedbacks:
                _cmt = []
                for cmt in fb.comments:
                    _cmt.append(serializer.comment(cmt, cmt.participant))

                _f = serializer.feedback(fb, None, perm_dict[fb.id])
                _f["comments"] = _cmt
                _feedbacks.append(_f)

            _r = serializer.code_ref_simple(ref)
            _r["feedbacks"] = _feedbacks
            _refs.append(_r)

        result["refs"] = _refs
        return result

    def create_code_ref_if_not_exists(
        self,
        project_id: int,
        filename: str,
        line: str,
    ) -> CodeReference:
        ref = (
            self.db.query(CodeReference)
            .filter(CodeReference.project_id == project_id)
            .filter(CodeReference.file == filename)
            .filter(CodeReference.line == line)
            .first()
        )

        if not ref:
            ref = CodeReference(project_id=project_id, file=filename, line=line)
            self.db.add(ref)
            self.db.commit()

        return ref

    def create_feedback(
        self,
        owner_id: int,
        filename: str,
        line: str,
        acl: list[int],
        comment: str,
    ) -> tuple[Feedback, Comment]:
        """Create a feedback with first comment attached

        Args:
            owner_id (int): file owner's participant ID
            filename (str): filename
            line (str): code ref line.
            acl (list[int]): participant IDs who can see this feedback
            comment (str): content of the created feedback comment

        TODO: file and line existence check
        """

        # Check readability to the file
        proj_file_ctrl = ProjectFileController(
            user_id=self.user_id, course_id=self.course_id, lesson_id=self.lesson_id, db=self.db
        )
        target_ptc, target_proj = proj_file_ctrl.get_target_info(target_ptc_id=owner_id, check_perm=PROJ_PERM.READ)

        # Check existence of the reference
        ref = self.create_code_ref_if_not_exists(target_proj.id, filename, line)

        # Create Feedback record
        feedback = Feedback(code_ref_id=ref.id, participant_id=self.my_participant.id)
        self.db.add(feedback)
        self.db.flush()

        # Create Comment record
        comment = Comment(
            feedback_id=feedback.id,
            participant_id=self.my_participant.id,
            content=comment,
        )
        self.db.add(comment)

        # Create ACL record
        acl.append(owner_id)
        acl_ptcs = (
            self.db.query(Participant)
            .filter(Participant.course_id == self.course_id)
            .filter(Participant.id.in_(acl))
            .all()
        )

        result_acl = []
        for target_ptc in acl_ptcs:
            result_acl.append(target_ptc.id)
            row = FeedbackViewerMap(feedback_id=feedback.id, participant_id=target_ptc.id)
            self.db.add(row)

        self.db.commit()

        return dict(
            feedback=feedback,
            comment=comment,
            acl=result_acl,
        )

    def modify_feedback(
        self,
        feedback_id: int,
        new_acl: list[int],
        new_resolved: bool,
    ) -> dict[str, Any]:
        """Modify feedback data

        Args:
            feedback_id (int): Feedback.id to modify
            new_acl (list[int]): participant IDs who can see this feedback
            new_resolved (bool: resolved or not

        Returns:
            dict[str, Any]: feedback and new acl
        """

        feedback: Feedback = (
            self.db.query(Feedback)
            .filter(Feedback.id == feedback_id)
            .options(joinedload(Feedback.viewer_map))
            .options(joinedload(Feedback.code_reference).joinedload(CodeReference.project))
            .first()
        )

        if not feedback:
            raise FeedbackNotFoundException("존재하지 않는 피드백입니다.")

        if feedback.participant_id != self.my_participant.id:
            raise FeedbackNotAuthException("해당 피드백에 대한 권한이 없습니다.")

        # Update ACL
        acls: dict[int, FeedbackViewerMap] = {perm.participant_id: perm for perm in feedback.viewer_map}
        result_acl = acl_valid_ptc = set([ptc_id for ptc_id, perm in acls.items() if perm.valid is True])

        # Make sure the project owner has permission
        owner_id = feedback.code_reference.project.participant_id
        new_acl.append(owner_id)
        if acl_valid_ptc != new_acl:
            acl_added_ptc = set(new_acl) - acl_valid_ptc
            acl_removed_ptc = acl_valid_ptc - set(new_acl)
            result_acl = list(acl_valid_ptc - acl_removed_ptc)  # First, not changed acls

            # Grant
            ptcs_to_grant: list[Participant] = (
                self.db.query(Participant)
                .filter(Participant.course_id == self.course_id)
                .filter(Participant.id.in_(acl_added_ptc))
                .all()
            )
            for ptc in ptcs_to_grant:  # This filters out non-existing participants
                result_acl.append(ptc.id)
                if ptc.id in acls.keys():  # If `invalid`` record already exists
                    acls[ptc.id].valid = True
                    self.db.add(acls[ptc.id])
                else:  # Create new one
                    self.db.add(FeedbackViewerMap(feedback_id=feedback_id, participant_id=ptc.id))

            # Revoke
            for ptc_id in acl_removed_ptc:
                acls[ptc_id].valid = False
                self.db.add(acls[ptc_id])

        # Update resolved status
        if new_resolved != feedback.resolved:
            feedback.resolved = new_resolved
            self.db.add(feedback)

        self.db.commit()

        return {
            "feedback": feedback,
            "acl": result_acl,
        }

    def create_comment(
        self,
        feedback_id: int,
        content: str,
    ) -> dict:
        """Create a comment on specified feedback

        Args:
            feedback_id (int): Feedback where created comment is attached
            comment (str): content of the comment

        Returns:
            dict: Feedback, Comment
        """

        row = (
            self.db.query(Feedback, FeedbackViewerMap)
            .filter(Feedback.id == feedback_id)
            .join(
                FeedbackViewerMap,
                and_(
                    FeedbackViewerMap.feedback_id == Feedback.id,
                    FeedbackViewerMap.participant_id == self.my_participant.id,
                ),
                isouter=True,
            )
            .options(
                joinedload(Feedback.code_reference)
                .joinedload(CodeReference.project)
                .joinedload(UserProject.participant)
            )
            .first()
        )
        if not row:
            raise FeedbackNotFoundException("존재하지 않는 피드백입니다.")

        feedback: Feedback = row[0]
        perm: FeedbackViewerMap = row[1]

        if not feedback:
            raise FeedbackNotFoundException("존재하지 않는 피드백입니다.")
        elif not perm:
            raise FeedbackNotAuthException("해당 피드백에 대한 권한이 없습니다.")

        cmt = Comment(feedback_id=feedback.id, participant_id=self.my_participant.id, content=content)
        self.db.add(cmt)
        self.db.commit()

        acl = [perm.participant_id for perm in feedback.viewer_map]

        return dict(
            feedback=feedback,
            comment=cmt,
            acl=acl,
        )

    def modify_comment(self, comment_id: int, new_content: str | None, to_delete: bool | None):
        cmt: Comment = (
            self.db.query(Comment)
            .filter(Comment.id == comment_id)
            .filter(Comment.deleted.is_(False))
            .options(
                joinedload(Comment.feedback)
                .joinedload(Feedback.code_reference)
                .joinedload(CodeReference.project)
                .joinedload(UserProject.participant)
            )
            .first()
        )

        if not cmt:
            raise FeedbackNotFoundException("존재하지 않는 댓글입니다.")

        if cmt.participant_id != self.my_participant.id:
            raise FeedbackNotAuthException("해당 댓글에 대한 수정 권한이 없습니다.")

        dirty = False
        if new_content:
            cmt.content = new_content
            dirty = True

        if to_delete:
            cmt.deleted = True
            dirty = True

        if dirty:
            self.db.add(cmt)
            self.db.commit()

        acl = [perm.participant_id for perm in cmt.feedback.viewer_map]

        return dict(
            feedback=cmt.feedback,
            comment=cmt,
            acl=acl,
        )
