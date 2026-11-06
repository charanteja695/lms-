"""Attachments on ticket messages: presigned direct-to-S3 uploads (the bytes never pass through this service), checked
against storage when a message is written, and short-lived download links for whoever may read that message."""

import uuid
from typing import Any

from app.core.config import Settings
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models.ticket import TicketMessage
from app.schemas.support import AttachmentIn
from app.storage import s3
from app.storage.keys import safe_filename, upload_prefix


def _invalid(field: str, code: str, message: str) -> ValidationFailedError:
    return ValidationFailedError(details=[{"field": field, "code": code, "message": message}])


class AttachmentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def max_bytes(self) -> int:
        return self.settings.ATTACHMENT_MAX_MB * 1024 * 1024

    def _check_type(self, filename: str, field: str) -> None:
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        allowed = [e.lower() for e in self.settings.ATTACHMENT_ALLOWED_EXTENSIONS]
        if extension not in allowed:
            raise _invalid(field, "INVALID_FILE_TYPE", f"Allowed file types: {', '.join(allowed)}")

    async def upload_url(self, user_id: int, *, filename: str, content_type: str, size_bytes: int) -> dict[str, Any]:
        self._check_type(filename, "filename")
        if size_bytes > self.max_bytes:
            raise _invalid("size_bytes", "OUT_OF_RANGE", f"Files can be up to {self.settings.ATTACHMENT_MAX_MB} MB")
        key = f"{upload_prefix(user_id)}{uuid.uuid4().hex}/{safe_filename(filename)}"
        upload = await s3.presign_upload(
            self.settings, key, content_type=content_type, max_bytes=self.max_bytes, expires_seconds=self.settings.S3_UPLOAD_URL_EXPIRES_SECONDS
        )
        return {"key": key, "upload": upload, "expires_in": self.settings.S3_UPLOAD_URL_EXPIRES_SECONDS}

    async def verify(self, user_id: int, items: list[AttachmentIn]) -> list[dict[str, Any]] | None:
        """The stored form of a message's attachments: each must be the author's own upload and really be in storage."""
        if not items:
            return None
        if len(items) > self.settings.ATTACHMENT_MAX_FILES:
            raise _invalid("attachments", "TOO_MANY_FILES", f"Attach up to {self.settings.ATTACHMENT_MAX_FILES} files")
        stored: list[dict[str, Any]] = []
        for i, item in enumerate(items):
            field = f"attachments.{i}"
            if not item.key.startswith(upload_prefix(user_id)) or ".." in item.key:
                raise _invalid(field, "NOT_YOUR_FILE", "This file was not uploaded by you.")
            self._check_type(item.filename, field)
            try:
                head = await s3.head_object(self.settings, item.key)
            except s3.ObjectNotFound:
                raise _invalid(field, "FILE_NOT_UPLOADED", "The file has not finished uploading.") from None
            size = int(head.get("ContentLength", 0))
            if not 0 < size <= self.max_bytes:
                raise _invalid(field, "OUT_OF_RANGE", f"Files can be up to {self.settings.ATTACHMENT_MAX_MB} MB")
            stored.append({"key": item.key, "filename": item.filename, "content_type": str(head.get("ContentType") or "application/octet-stream"), "size_bytes": size})
        return stored

    async def download_url(self, message: TicketMessage, index: int) -> dict[str, Any]:
        files = message.attachments or []
        if not 0 <= index < len(files):
            raise NotFoundError("Attachment not found.", code="ATTACHMENT_NOT_FOUND")
        url = await s3.presign_get(self.settings, files[index]["key"], expires_seconds=self.settings.S3_DOWNLOAD_URL_EXPIRES_SECONDS)
        return {"filename": files[index]["filename"], "url": url, "expires_in": self.settings.S3_DOWNLOAD_URL_EXPIRES_SECONDS}
