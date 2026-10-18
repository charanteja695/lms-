"""Thin async wrapper around boto3 S3. boto3 is synchronous, so every call runs in a worker
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
        "config": BotoConfig(signature_version="s3v4", s3={"addressing_style": "virtual"} if not settings.S3_ENDPOINT_URL else {}),
    }
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID.get_secret_value()
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY.get_secret_value()
    # Always the bucket's own regional address: the global one (bucket.s3.amazonaws.com) redirects for buckets outside
    # us-east-1, and a redirected presigned link no longer matches its signature (the browser gets 403).
    kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL or f"https://s3.{settings.AWS_REGION}.amazonaws.com"
    return boto3.client("s3", **kwargs)


class ObjectNotFound(Exception):
    pass


async def presign_upload(
    settings: Settings, key: str, *, content_type: str, max_bytes: int, expires_seconds: int
) -> dict[str, Any]:
    """A presigned POST: the browser uploads directly to S3 with these fields, never through us."""

    def _presign() -> dict[str, Any]:
        return cast(
            "dict[str, Any]",
            _client(settings).generate_presigned_post(
                Bucket=settings.S3_BUCKET,
                Key=key,
                Fields={"Content-Type": content_type},
                Conditions=[
                    {"Content-Type": content_type},
                    ["content-length-range", 1, max_bytes],
                ],
                ExpiresIn=expires_seconds,
            ),
        )

    return await to_thread.run_sync(_presign)


async def presign_get(
    settings: Settings, key: str, *, expires_seconds: int, content_type: str | None = None, disposition: str | None = None
) -> str:
    """``content_type``/``disposition`` override what the browser is told, e.g. to show a PDF inline."""
    params: dict[str, str] = {"Bucket": settings.S3_BUCKET, "Key": key}
    if content_type:
        params["ResponseContentType"] = content_type
    if disposition:
        params["ResponseContentDisposition"] = disposition

    def _presign() -> str:
        return cast(str, _client(settings).generate_presigned_url("get_object", Params=params, ExpiresIn=expires_seconds))

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


async def read_prefix(settings: Settings, key: str, length: int) -> bytes:
    """The first ``length`` bytes of an object (a ranged GET), e.g. to check a file's signature."""

    def _read() -> bytes:
        response = _client(settings).get_object(Bucket=settings.S3_BUCKET, Key=key, Range=f"bytes=0-{length - 1}")
        return cast(bytes, response["Body"].read())

    return await to_thread.run_sync(_read)


async def delete_object(settings: Settings, key: str) -> None:
    def _delete() -> None:
        _client(settings).delete_object(Bucket=settings.S3_BUCKET, Key=key)

    await to_thread.run_sync(_delete)


async def download_file(settings: Settings, key: str, local_path: str) -> None:
    """Used by the transcoding pipeline (see app/pipeline): ffmpeg needs a local file, not a URL."""

    def _download() -> None:
        _client(settings).download_file(settings.S3_BUCKET, key, local_path)

    await to_thread.run_sync(_download)


async def upload_file(settings: Settings, local_path: str, key: str, *, content_type: str) -> None:
    def _upload() -> None:
        _client(settings).upload_file(local_path, settings.S3_BUCKET, key, ExtraArgs={"ContentType": content_type})

    await to_thread.run_sync(_upload)
