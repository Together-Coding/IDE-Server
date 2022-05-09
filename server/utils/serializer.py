from typing import Any

from server.models.course import Participant, ProjectViewer, UserProject


def accessible_user(part: Participant, proj: UserProject, perm: ProjectViewer) -> dict[str, Any]:
    """자신의/다른 유저의 접근 권한에 대한 데이터를 serialize

    Args:
        part (Participant): _description_
        proj (UserProject): _description_
        perm (ProjectViewer): _description_

    Returns:
        _type_: _description_
    """
    
    return {
        "id": part.id,
        "userId": part.user_id,
        "nickname": part.nickname,
        "role": part.role,
        "active": proj.active if proj else False,
        "permission": perm.permission if perm else 0,
    }
