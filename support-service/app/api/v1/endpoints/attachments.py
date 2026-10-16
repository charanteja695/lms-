"""Upload URLs for attachments. The file goes straight to storage; its `key` is then sent with the ticket or reply."""

from fastapi import APIRouter

from app.api.deps import AttachmentRateLimit, RequireParticipant, SettingsDep
from app.api.responses import AUTHENTICATED, errors
from app.schemas.support import AttachmentUpload, AttachmentUploadRequest, AttachmentUploadResponse
from app.services.attachment_service import AttachmentService

router = APIRouter(prefix="/attachments", tags=["Attachments"])


@router.post(
    "/upload-url", response_model=AttachmentUploadResponse, summary="Get a URL to upload one attachment",
    description="Checks the file type and size (`ATTACHMENT_ALLOWED_EXTENSIONS`, `ATTACHMENT_MAX_MB`) and returns a presigned POST. "
    "Upload the file to it, then list `{key, filename}` in the `attachments` of a new ticket or a reply.",
    responses=errors(*AUTHENTICATED), dependencies=[AttachmentRateLimit],
)
async def upload_url(body: AttachmentUploadRequest, auth: RequireParticipant, settings: SettingsDep) -> AttachmentUploadResponse:
    issued = await AttachmentService(settings).upload_url(auth.user_id, filename=body.filename, content_type=body.content_type, size_bytes=body.size_bytes)
    return AttachmentUploadResponse(message="", attachment=AttachmentUpload.model_validate(issued))
