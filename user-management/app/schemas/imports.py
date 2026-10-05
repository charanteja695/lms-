from pydantic import Field

from app.schemas.common import ResponseSchema, SuccessResponse


class ImportRowError(ResponseSchema):
    row: int = Field(description="Spreadsheet row number (the header is row 1)", examples=[5])
    column: str | None = Field(examples=["phone"])
    code: str = Field(examples=["INVALID_PHONE"])
    message: str = Field(examples=["Enter a valid phone number, e.g. +919876543210"])


class ImportedUser(ResponseSchema):
    row: int
    user_id: str
    email: str | None
    username: str
    temporary_password: str | None = Field(
        default=None, description="Generated for students without email. Shown only in this response."
    )


class ImportResultOut(ResponseSchema):
    dry_run: bool
    mode: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    created: int
    created_users: list[ImportedUser]
    errors: list[ImportRowError]


class ImportResponse(SuccessResponse):
    import_result: ImportResultOut
