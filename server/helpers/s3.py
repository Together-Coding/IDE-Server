from io import BufferedReader

import boto3
from botocore.errorfactory import ClientError

from configs import settings

_s3 = boto3.client("s3", region_name="ap-northeast-2")


def get_object(key: str, bucket: str = settings.S3_BUCKET):
    key = key.strip("/")
    return _s3.get_object(Bucket=bucket, Key=key)


def put_object(body: BufferedReader, key: str, bucket: str = settings.S3_BUCKET, acl="private"):
    body.seek(0)

    return _s3.put_object(
        ACL=acl,
        Body=body.read(),
    )


def is_exists(key: str, bucket: str = settings.S3_BUCKET):
    try:
        _s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError:
        return False
