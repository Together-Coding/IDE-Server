from io import BufferedReader

import boto3
from botocore.errorfactory import ClientError

from configs import settings

_s3 = boto3.client("s3", region_name="ap-northeast-2")


def _refine_key(key: str):
    """Refine S3 object key; as the leading slash(/) is treated as filename, 
    it should be removed.

    Args:
        key (str): _description_

    Returns:
        _type_: _description_
    """

    return key.strip("/")


def get_object(key: str, bucket: str | None = None):
    if not bucket:
        bucket = settings.S3_BUCKET

    return _s3.get_object(Bucket=bucket, Key=_refine_key(key))


def put_object(body: BufferedReader, key: str, bucket: str | None = None, acl="private"):
    if not bucket:
        bucket = settings.S3_BUCKET

    body.seek(0)
    return _s3.put_object(ACL=acl, Body=body.read(), Key=_refine_key(key))


def is_exists(key: str, bucket: str | None = None):
    if not bucket:
        bucket = settings.S3_BUCKET

    try:
        _s3.head_object(Bucket=bucket, Key=_refine_key(key))
        return True
    except ClientError:
        return False

def delete_object(key: str, bucket: str| None = None):
    if not bucket:
        bucket = settings.S3_BUCKET

    return _s3.delete_object(Bucket=bucket, Key=key)