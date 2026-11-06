"""File and project answers: presigned direct-to-S3 uploads (the bytes never pass through this service) and
short-lived download links for graders."""

import uuid
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError
from app.core.security import AccessTokenClaims
from app.domain.enums import QuestionType
from app.models.attempt import AttemptAnswer
from app.permissions.policy import can_grade_attempt, can_view_attempt
from app.services.answer_service import file_prefix
from app.services.attempt_service import AttemptService
from app.storage import s3
from app.storage.keys import safe_filename


class FileService:
    def __init__(self, db: AsyncSession, settings: Settings, redis: Redis | None = None) -> None:
        self.db = db
        self.settings = settings
        self.attempts = AttemptService(db, settings, redis)

    async def upload_url(
        self, user_id: int, attempt_public_id: int, question_public_id: int, *, filename: str, content_type: str, size_bytes: int
    ) -> dict[str, Any]:
        meta = await self.attempts.gate(attempt_public_id, user_id)
        paper = {int(q["question_id"]): q for q in await self.attempts.paper(attempt_public_id, uuid.UUID(meta.attempt_id))}
        question = paper.get(question_public_id)
        if question is None:
            raise NotFoundError("Question not found.", code="QUESTION_NOT_IN_ATTEMPT")
        if question["question_type"] != QuestionType.FILE_SUBMISSION:
            raise ConflictError("This question does not take files.", code="NOT_A_FILE_QUESTION")
        body = question["body"]
        limit = body["max_size_mb"] * 1024 * 1024
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        allowed = body.get("allowed_extensions")
        if allowed and extension not in allowed:
            raise ValidationFailedError(details=[{"field": "filename", "code": "INVALID_FILE_TYPE", "message": f"Allowed file types: {', '.join(allowed)}"}])
        if not 0 < size_bytes <= limit:
            raise ValidationFailedError(details=[{"field": "size_bytes", "code": "OUT_OF_RANGE", "message": f"Files can be up to {body['max_size_mb']} MB"}])
        key = f"{file_prefix(attempt_public_id, question_public_id)}{uuid.uuid4().hex}/{safe_filename(filename)}"
        upload = await s3.presign_upload(
            self.settings, key, content_type=content_type, max_bytes=limit, expires_seconds=self.settings.S3_UPLOAD_URL_EXPIRES_SECONDS
        )
        return {"key": key, "upload": upload, "expires_in": self.settings.S3_UPLOAD_URL_EXPIRES_SECONDS}

    async def download_url(self, auth: AccessTokenClaims, attempt_public_id: int, question_public_id: int, index: int) -> dict[str, Any]:
        attempt = await self.attempts.get(attempt_public_id)
        test = await self.attempts.test_of(attempt)
        if not can_view_attempt(auth, attempt_user_id=attempt.user_id, attempt_organization_id=attempt.organization_id, test_owner_id=test.organization_id) or (
            auth.user_id != attempt.user_id
            and not can_grade_attempt(auth, attempt_organization_id=attempt.organization_id, test_owner_id=test.organization_id)
        ):
            raise PermissionDeniedError()
        answer = (
            await self.db.execute(
                select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt.id, AttemptAnswer.question_public_id == question_public_id)
            )
        ).scalar_one_or_none()
        files = (answer.response or {}).get("files", []) if answer else []
        if not 0 <= index < len(files):
            raise NotFoundError("File not found.", code="FILE_NOT_FOUND")
        url = await s3.presign_get(self.settings, files[index]["key"], expires_seconds=self.settings.S3_DOWNLOAD_URL_EXPIRES_SECONDS)
        return {"filename": files[index]["filename"], "url": url, "expires_in": self.settings.S3_DOWNLOAD_URL_EXPIRES_SECONDS}
