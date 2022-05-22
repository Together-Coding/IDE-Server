from typing import Any

from server.models.course import PROJ_PERM, Participant, ProjectViewer, UserProject


def accessible_user(
    part: Participant,
    proj: UserProject,
    perm: ProjectViewer,
    no_perm_val=0,
) -> dict[str, Any]:
    """자신의/다른 유저의 접근 권한에 대한 데이터를 serialize

    Args:
        part (Participant): 유저의 수업 참여 정보
        proj (UserProject): 유저의 project 정보
        perm (ProjectViewer): 유저의 타 유저 프로젝트 접근 권한

    Returns:
        dict[str, Any]: serialized dict
    """

    return {
        "userId": part.id,  # Participant ID
        "projectId": proj.id,
        "nickname": part.nickname,
        "role": part.role,
        "active": proj.active if proj else False,
        "permission": perm.permission if perm else no_perm_val,
    }


def permission_modified(target_id: int, perm: ProjectViewer) -> dict[str, Any]:
    """변경된 접근 권한에 대한 데이터를 serialize

    Args:
        target_id (int): 변경을 요청한 유저의 Participant ID
        perm (ProjectViewer): 타 유저 프로젝트 접근 권한

    Returns:
        dict[str, Any]: serialized dict
    """

    return {
        "userId": perm.viewer_id,  # 권한이 변경된 유저 Participant ID
        "targetId": target_id,  # 변경을 요청한 유저 Participant ID
        "permission": perm.permission,
        "added": perm.added,  # 추가된 권한
        "removed": perm.removed,  # 제거된 권한
    }
