from constants.ws import WSEvent
from server import sio
from server.controllers.feedback import FeedbackController
from server.helpers import sentry
from server.helpers.db import get_db
from server.utils.exceptions import BaseException
from server.utils.response import ws_error_response
from server.websockets.decorators import in_lesson


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

    owner_id = data.get("ownerId") if data else None
    file = data.get("file") if data else None

    try:
        fb_ctrl = await FeedbackController.from_session(sid, get_db())
        data = fb_ctrl.get_feedbacks(owner_id, file)

        await sio.emit(WSEvent.FEEDBACK_LIST, data=data, to=sid)
    except BaseException as e:
        await sio.emit(WSEvent.FEEDBACK_LIST, data=ws_error_response(e.error), to=sid)
    except:
        sentry.exc()
