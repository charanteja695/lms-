"""Thin async wrapper around boto3 S3 for generated certificates. boto3 is synchronous, so every call runs in a worker
thread (``anyio.to_thread``) to avoid blocking the event loop. This is the only place that
imports boto3 — swap the implementation here if the storage backend ever changes.

Every function takes ``settings`` explicitly (never the global ``get_settings()`` singleton),
so callers control exactly which configuration is used — this is what lets tests point at a
mocked bucket without touching process-wide state.
"""

from typing import Any, cast

import boto3
from anyio import to_thread
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import Settings


def _client(settings: Settings) -> Any:
    kwargs: dict[str, Any] = {
        "region_name": settings.AWS_REGION,
        "config": BotoConfig(signature_version="s3v4"),
    }
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID.get_secret_value()
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY.get_secret_value()
    if settings.S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
    return boto3.client("s3", **kwargs)


class ObjectNotFound(Exception):
    pass


async def put_object(settings: Settings, key: str, body: bytes, *, content_type: str) -> None:
    def _put() -> None:
        _client(settings).put_object(Bucket=settings.S3_BUCKET, Key=key, Body=body, ContentType=content_type)

    await to_thread.run_sync(_put)


async def presign_get(settings: Settings, key: str, *, expires_seconds: int) -> str:
    def _presign() -> str:
        return cast(
            str,
            _client(settings).generate_presigned_url(
                "get_object", Params={"Bucket": settings.S3_BUCKET, "Key": key}, ExpiresIn=expires_seconds
            ),
        )

    return await to_thread.run_sync(_presign)


async def head_object(settings: Settings, key: str) -> dict[str, Any]:
    def _head() -> dict[str, Any]:
        try:
            return cast("dict[str, Any]", _client(settings).head_object(Bucket=settings.S3_BUCKET, Key=key))
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                raise ObjectNotFound(key) from exc
            raise

    return await to_thread.run_sync(_head)


async def delete_object(settings: Settings, key: str) -> None:
    def _delete() -> None:
        _client(settings).delete_object(Bucket=settings.S3_BUCKET, Key=key)

    await to_thread.run_sync(_delete)
