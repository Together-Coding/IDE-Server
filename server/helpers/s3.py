from io import IOBase

import boto3
from botocore.errorfactory import ClientError

from configs import settings

_s3 = boto3.client("s3", region_name="ap-northeast-2")


def _refine_key(key: str) -> str:
    """Refine S3 object key; as the leading slash(/) is treated as filename,
    it should be removed.

    Args:
        key (str): S3 object key

    Returns:
        str: Refined S3 object key
    """

    return key.strip("/")


def get_object(key: str, bucket: str | None = None):
    if not bucket:
        bucket = settings.S3_BUCKET

    return _s3.get_object(Bucket=bucket, Key=_refine_key(key))


def put_object(body: IOBase, key: str, bucket: str | None = None, acl="private"):
    if not bucket:
        bucket = settings.S3_BUCKET

    body.seek(0)
    return _s3.put_object(
        Bucket=bucket,
        Key=_refine_key(key),
        ACL=acl,
        Body=body.read(),
    )


def is_exists(key: str, bucket: str | None = None):
    if not bucket:
        bucket = settings.S3_BUCKET

    try:
        _s3.head_object(Bucket=bucket, Key=_refine_key(key))
        return True
    except ClientError:
        return False


def delete_object(key: str, bucket: str | None = None):
    if not bucket:
        bucket = settings.S3_BUCKET

    return _s3.delete_object(Bucket=bucket, Key=key)
