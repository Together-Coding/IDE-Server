from typing import Any
import datetime

from server.models.course import Participant, ProjectViewer, UserProject


def iso8601(dt: datetime.datetime):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def participant(ptc: Participant, proj: UserProject) -> dict[str, Any]:
    """수업 참여자에 대한 public 데이터를 serialize

    Args:
        ptc (Participant): user's participant record
        proj (UserProject): user's Project record

    Returns:
        dict[str, Any]: serialized dict
    """

    data = {
        "id": ptc.id,
        "is_teacher": ptc.is_teacher,
        "nickname": ptc.nickname,
    }
    if proj:
        data["project"] = {
            "id": proj.id,
            "active": proj.active,
            "created_at": iso8601(proj.created_at),
        }
    else:
        data["project"] = None

    return data


def accessible_user(part: Participant, proj: UserProject, perm: ProjectViewer) -> dict[str, Any]:
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
        "permission": perm.permission if perm else 0,
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
