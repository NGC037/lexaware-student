from __future__ import annotations

from typing import Protocol, cast

import boto3
from botocore.config import Config

from app.core.config import get_settings


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class S3ObjectStorage:
    """Private S3-compatible storage; callers receive no public or presigned URLs."""

    def __init__(self) -> None:
        settings = get_settings()
        self._bucket = settings.s3_bucket
        self._max_bytes = settings.document_max_upload_bytes
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=30),
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def get(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        body = response["Body"]
        try:
            payload = cast(bytes, body.read(self._max_bytes + 1))
            if len(payload) > self._max_bytes:
                raise ValueError("Stored PDF exceeds the configured byte limit.")
            return payload
        finally:
            body.close()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)
