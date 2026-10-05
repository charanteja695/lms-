from lms_common.envelopes import RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.run import SourceCode
from app.schemas.types import PublicIdOut, Timestamp


class SavedCodeUpdate(RequestSchema):
    source: SourceCode


class SavedCodeOut(ResponseSchema):
    problem_id: PublicIdOut
    language: str
    source: str
    updated_at: Timestamp | None = Field(description="None when nothing has been saved: source is then the starter template")


class SavedCodeResponse(SuccessResponse):
    saved_code: SavedCodeOut  # not `code`: that name is the envelope's SUCCESS code
