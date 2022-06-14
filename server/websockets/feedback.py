from typing import Any


from server.utils import serializer
from constants.ws import WSEvent
from server import sio
from server.controllers.feedback import FeedbackController
from server.helpers import sentry
from server.helpers.db import get_db
from server.models.feedback import Feedback, Comment
from server.utils.exceptions import BaseException, MissingFieldException
from server.utils.response import ws_error_response
from server.utils.serializer import iso8601
from server.websockets import session as ws_session
from server.websockets.decorators import in_lesson, requires


def check_code_ref(ref: dict):
    errs = []
    if type(ref) != dict:
        errs.append("`ref` must be object type.")
    else:
        for key in ["ownerId", "file", "line"]:
            if key not in ref:
                errs.append(f"`ref.{key}` is required.")

    if errs:
        raise MissingFieldException(errs)


@sio.on(WSEvent.FEEDBACK_LIST)
@in_lesson
async def get_feedback_list(sid: str, data: dict = None):
    """Return feedback list depending on data.
    If data is None, this returns all feedbacks that requestor can access to.
    Otherwise, returns feedbacks on specific file.

    - data = None
    - data = {
        ownerId (int): owner user's participant ID
        file (str): filename
    }
    """

    if not data:
        data = {}

    owner_id = data.get("ownerId") if data else None
    file = data.get("file") if data else None

    try:
        fb_ctrl = await FeedbackController.from_session(sid, get_db())
        if owner_id and file:
            resp = fb_ctrl.get_feedbacks(owner_id, file)
        else:
            resp = fb_ctrl.get_all_feedbacks()

        await sio.emit(WSEvent.FEEDBACK_LIST, data=resp, to=sid, uuid=data.get("uuid"))
    except BaseException as e:
        await sio.emit(WSEvent.FEEDBACK_LIST, data=ws_error_response(e.error), to=sid, uuid=data.get("uuid"))
    except:
        sentry.exc()


@sio.on(WSEvent.FEEDBACK_ADD)
@requires(WSEvent.FEEDBACK_ADD, ["ref", "acl", "comment"])
@in_lesson
async def add_feedback(sid: str, data: dict):
    """Create a feedback with first comment attached.

    data: {
        ref (dict): {
            ownerId (int): file owner's participant ID
            file (str): filename
            line (str): code ref line. (ex. '11-14' meaning line number 11~14 )
        },
        acl (list[int]): participant IDs who can see this feedback
        comment (str): content of the created feedback comment
    }
    """

    try:
        ref: dict[str, Any] = data.get("ref")
        acl: list[int] = data.get("acl")
        comment: str = data.get("comment")

        # Validation
        check_code_ref(ref)
        if type(acl) != list:
            raise MissingFieldException("`acl` must be array type.")

        # Parse again
        owner_id = ref["ownerId"]
        filename = ref["file"]
        line = ref["line"]

        # Logic
        fb_ctrl = await FeedbackController.from_session(sid, get_db())
        result = fb_ctrl.create_feedback(owner_id, filename, line, acl, comment)

        feedback: Feedback = result["feedback"]
        comment: Comment = result["comment"]
        acl: list[int] = result["acl"]

        resp = {
            "ref": serializer.code_ref_from_feedback(feedback),
            "feedback": serializer.feedback(feedback, fb_ctrl.my_participant, acl),
            "comment": serializer.comment(comment),
        }

        # Send to participants
        for ptc_id in acl:
            target_sid = ws_session.get_ptc_sid(fb_ctrl.course_id, fb_ctrl.lesson_id, ptc_id)
            if target_sid:
                await sio.emit(
                    WSEvent.FEEDBACK_ADD,
                    data=resp,
                    to=target_sid,
                    uuid=data.get("uuid"),
                )

    except BaseException as e:
        await sio.emit(WSEvent.FEEDBACK_ADD, data=ws_error_response(e.error), to=sid, uuid=data.get("uuid"))
    except:
        sentry.exc()


@sio.on(WSEvent.FEEDBACK_MOD)
@requires(WSEvent.FEEDBACK_MOD, ["feedbackId", "acl", "resolved"])
@in_lesson
async def modify_feedback(sid: str, data: dict):
    """Modify feedback data

    data: {
        feedbackId (int): Feedback.id to modify
        acl (list[int]): participant IDs who can see this feedback
        resolved (bool): resolved or not
    }
    """

    try:
        feedback_id = data.get("feedbackId")
        acl = data.get("acl")
        resolved = data.get("resolved")

        if type(acl) != list:
            raise MissingFieldException("`acl` must be array type.")

        fb_ctrl = await FeedbackController.from_session(sid, get_db())
        result = fb_ctrl.modify_feedback(feedback_id, acl, resolved)

        feedback: Feedback = result["feedback"]
        result_acl: list[int] = result["acl"]

        resp = {
            "ref": serializer.code_ref_from_feedback(feedback),
            "feedback": serializer.feedback(feedback, fb_ctrl.my_participant, result_acl),
        }

        # Send to participants
        for ptc_id in result_acl:
            target_sid = ws_session.get_ptc_sid(fb_ctrl.course_id, fb_ctrl.lesson_id, ptc_id)
            if target_sid:
                await sio.emit(
                    WSEvent.FEEDBACK_MOD,
                    data=resp,
                    to=target_sid,
                    uuid=data.get("uuid"),
                )

    except BaseException as e:
        await sio.emit(WSEvent.FEEDBACK_MOD, data=ws_error_response(e.error), to=sid, uuid=data.get("uuid"))
    except:
        sentry.exc()


@sio.on(WSEvent.FEEDBACK_COMMENT)
@requires(WSEvent.FEEDBACK_COMMENT, ["feedbackId", "content"])
@in_lesson
async def create_comment(sid: str, data: dict):
    feedback_id = data.get("feedbackId")
    content = data.get("content")

    try:
        fb_ctrl = await FeedbackController.from_session(sid, get_db())
        result = fb_ctrl.create_comment(feedback_id, content)

        feedback: Feedback = result["feedback"]
        comment: Comment = result["comment"]
        acl: list[int] = result["acl"]

        # According to frontend developer's request, modified the response format.
        all_data = fb_ctrl.get_all_feedbacks()
        resp: list[dict] = []  # all comments in this lesson
        _refs = {}
        _fbs = {}
        for data in all_data:
            resp.extend(data.get('comments', []))
            for _fb in data.get('feedbacks', []):
                _fbs[_fb['id']] = _fb
            for _ref in data.get('refs', []):
                _refs[_ref['id']] = _ref

        for cmt in resp:
            _fb = _fbs.get(cmt['feedbackId'])
            if not _fb:
                continue
            _ref = _refs.get(_fb['refId'])
            if not _ref:
                continue
            
            cmt['feedbackFileName'] = _ref['file']
            cmt['feedbackLine'] = _ref['line']

        # Sent to participants
        for ptc_id in acl:
            target_sid = ws_session.get_ptc_sid(fb_ctrl.course_id, fb_ctrl.lesson_id, ptc_id)
            if target_sid:
                await sio.emit(
                    WSEvent.FEEDBACK_COMMENT,
                    data=resp,
                    to=target_sid,
                    uuid=data.get("uuid"),
                )
    except BaseException as e:
        await sio.emit(WSEvent.FEEDBACK_COMMENT, data=ws_error_response(e.error), to=sid, uuid=data.get("uuid"))
    except:
        sentry.exc()


@sio.on(WSEvent.FEEDBACK_COMMENT_MOD)
@requires(WSEvent.FEEDBACK_COMMENT_MOD, ["commentId"])
@in_lesson
async def modify_comment(sid: str, data: dict):
    comment_id: int = data.get("commentId")
    content: str | None = data.get("content")
    to_delete: bool | None = data.get("delete")

    try:
        fb_ctrl = await FeedbackController.from_session(sid, get_db())

        # 본인만 수정할 수 있다고 가정
        result = fb_ctrl.modify_comment(comment_id, content, to_delete)

        feedback: Feedback = result["feedback"]
        comment: Comment = result["comment"]
        acl: list[int] = result["acl"]

        resp = {
            "ref": serializer.code_ref_from_feedback(feedback),
            "feedback": serializer.feedback(feedback, feedback.participant, acl),
            "comment": serializer.comment(comment, fb_ctrl.my_participant),
        }

        # Sent to participants
        for ptc_id in acl:
            target_sid = ws_session.get_ptc_sid(fb_ctrl.course_id, fb_ctrl.lesson_id, ptc_id)
            if target_sid:
                await sio.emit(
                    WSEvent.FEEDBACK_COMMENT_MOD,
                    data=resp,
                    to=target_sid,
                    uuid=data.get("uuid"),
                )
    except BaseException as e:
        await sio.emit(WSEvent.FEEDBACK_COMMENT_MOD, data=ws_error_response(e.error), to=sid, uuid=data.get("uuid"))
    except:
        sentry.exc()
