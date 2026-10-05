"""Calibration against human-rated samples, and the fairness audit of a screening plan (docs/PRODUCT.md §5.8 "Fairness")."""

from typing import Any

from lms_common.envelopes import RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field

from app.schemas.types import PublicIdOut, Timestamp


class CalibrationTurnIn(RequestSchema):
    """The same shape a transcript's turns come in (``TurnOut``): copy them from a past interview to build a sample."""

    seq: int
    round: str
    speaker: str
    kind: str
    text: str
    elapsed_ms: int = 0


class CalibrationSampleRequest(RequestSchema):
    turns: list[CalibrationTurnIn] = Field(min_length=1, max_length=200)
    human_scores: dict[str, float] = Field(description="criterion -> a person's score, 1 to 5")
    human_recommendation: str


class CalibrationSampleOut(ResponseSchema):
    sample_id: PublicIdOut
    human_scores: dict[str, float]
    human_recommendation: str
    rated_by: PublicIdOut
    created_at: Timestamp


class CalibrationRunOut(ResponseSchema):
    run_id: PublicIdOut
    model: str | None
    prompt_version: int | None
    samples: int
    mean_abs_error: float | None
    within_one_rate: float | None
    recommendation_agreement: float | None
    details: list[dict[str, Any]]
    created_at: Timestamp


class CalibrationSampleResponse(SuccessResponse):
    sample: CalibrationSampleOut


class CalibrationSamplePage(SuccessResponse):
    samples: list[CalibrationSampleOut]


class CalibrationRunResponse(SuccessResponse):
    run: CalibrationRunOut


class CalibrationRunPage(SuccessResponse):
    runs: list[CalibrationRunOut]


class AuditReportOut(ResponseSchema):
    plan_id: str
    family_id: str
    interviews: int
    evaluated: int
    recommendations: dict[str, int]
    average_score: float | None
    reviewed: int
    override_rate: float | None
    invalid_quote_rate: float | None
    adverse_impact: dict[str, Any]
    calibration: dict[str, Any] | None
    note: str


class AuditReportResponse(SuccessResponse):
    audit: AuditReportOut
