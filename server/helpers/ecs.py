import boto3
from botocore.errorfactory import ClientError

from configs import settings
from server.helpers import sentry

_ecs = boto3.client("ecs", region_name="ap-northeast-2")


def run_task(num: int, *args, **kwargs) -> list[str]:
    task_arns = []
    for _ in range(num // 10):
        task_arns.extend(_run_task(count=10, *args, **kwargs))

    task_arns.extend(_run_task(count=num % 10, *args, **kwargs))

    return task_arns


def _run_task(count: int, started_by: str = ""):
    """
    Args:
        count (int): The number of instantiations of the specified task to place
                    on your cluster. You can specify up to ``10`` tasks for each call.
    """
    
    if count <= 0:
        return []

    resp = _ecs.run_task(
        cluster=settings.TEST_CLUSTER,
        count=count,
        group="toco",
        launchType=settings.TEST_TASK_TYPE,
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": settings.TEST_SUBNETS,
                "securityGroups": settings.TEST_SECURITY_GROUPS,
                "assignPublicIp": "DISABLED" if settings.TEST_TASK_TYPE == "EC2" else "ENABLED",
            }
        },
        startedBy=started_by,
        taskDefinition=settings.TEST_TASKDEF,
    )

    tasks = resp["tasks"]
    task_arns = list(map(lambda t: t["taskArn"], tasks))

    if resp["failures"]:
        sentry.msg(str(resp["failures"]))

    return task_arns
