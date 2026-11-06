from lms_common.envelopes import RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, Timestamp, id_field, raw_text, text

# Bytes are the real limit (Settings.MAX_SOURCE_BYTES, checked in the service); this only bounds what is parsed.
SourceCode = raw_text(400_000)
StdinText = raw_text(400_000)
LanguageRef = text(30, examples=["python3"])
RunProblemId = id_field("problem_id", "1755000000006555")


class RunCreate(RequestSchema):
    language: LanguageRef  # type: ignore[valid-type]
    source: SourceCode  # type: ignore[valid-type]
    stdin: StdinText = ""  # type: ignore[valid-type]
    problem_id: RunProblemId | None = Field(  # type: ignore[valid-type]
        default=None, description="SQL only: run the query against this problem's schema and sample data"
    )


class RunOut(ResponseSchema):
    run_id: PublicIdOut = Field(validation_alias="public_id")
    language: str = Field(validation_alias="language_code")
    status: str = Field(description="queued, running or completed; poll until completed")
    outcome: str | None = Field(description="ok, compilation_error, runtime_error, time_limit_exceeded, ... once completed")
    stdout: str | None
    stderr: str | None
    compile_output: str | None
    message: str | None
    time_ms: int | None
    memory_kb: int | None
    exit_code: int | None
    created_at: Timestamp
    finished_at: Timestamp | None


class RunResponse(SuccessResponse):
    run: RunOut


class InternalRunCreate(RequestSchema):
    """ai-interview-service running a candidate's code in the coding round."""

    user_id: id_field("user_id", "1755000000003001")  # type: ignore[valid-type]
    organization_id: id_field("organization_id", "1755000000004003") | None = None  # type: ignore[valid-type]
    language: LanguageRef  # type: ignore[valid-type]
    source: SourceCode  # type: ignore[valid-type]
    stdin: StdinText = ""  # type: ignore[valid-type]
