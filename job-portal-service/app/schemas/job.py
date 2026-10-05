from typing import Annotated, Any

from lms_common.envelopes import PageContext, RequestSchema, ResponseSchema, SuccessResponse
from pydantic import Field, model_validator
from pydantic_core import PydanticCustomError

from app.domain.enums import EmploymentType, LocationType
from app.schemas.fields import AwareDatetime, Percent, SkillList
from app.schemas.types import PublicIdOut, Timestamp, id_field, multiline_text, text

CourseId = id_field("Course", "1755000000001001")


# ---------------------------------------------------------------- request parts
class GraduationYears(RequestSchema):
    min: int | None = Field(default=None, ge=1990, le=2100)
    max: int | None = Field(default=None, ge=1990, le=2100)

    @model_validator(mode="after")
    def _ordered(self) -> "GraduationYears":
        if self.min is None and self.max is None:
            raise PydanticCustomError("REQUIRED", "Give a minimum year, a maximum year, or both")
        if self.min is not None and self.max is not None and self.max < self.min:
            raise PydanticCustomError("INVALID_RANGE", "The last year is before the first")
        return self


class MinScore(RequestSchema):
    course_id: CourseId  # type: ignore[valid-type]
    min_percent: Percent


class EligibilityIn(RequestSchema):
    graduation_years: GraduationYears | None = None
    certificate_course_ids: Annotated[list[CourseId], Field(max_length=10)] = Field(default_factory=list)  # type: ignore[valid-type]
    min_scores: Annotated[list[MinScore], Field(max_length=10)] = Field(default_factory=list)
    institution_ids: Annotated[list[id_field("Institution", "1755000000007003")], Field(max_length=200)] = Field(  # type: ignore[valid-type]
        default_factory=list, description="Empty: open to every institution. Otherwise the job is restricted to these institutions' students"
    )


class AssessmentStage(RequestSchema):
    test_id: id_field("Test", "1755000000000555")  # type: ignore[valid-type]
    min_percent: Percent | None = Field(default=None, description="Below this, the candidate is flagged for the recruiter (never rejected automatically)")


class InterviewStage(RequestSchema):
    plan_id: id_field("Interview plan", "1755000000000777")  # type: ignore[valid-type]


class PipelineIn(RequestSchema):
    """Which optional stages this job uses. A stage that is on cannot be skipped; one that is off cannot be entered."""

    assessment: AssessmentStage | None = None
    ai_interview: InterviewStage | None = None
    hr_interview: bool = False


class JobFields(RequestSchema):
    title: text(160, min_length=3)  # type: ignore[valid-type]
    description: multiline_text(8_000, min_length=1)  # type: ignore[valid-type]
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    location_type: LocationType = LocationType.ONSITE
    locations: Annotated[list[text(80)], Field(max_length=10)] = Field(default_factory=list)  # type: ignore[valid-type]
    experience_min_months: int = Field(default=0, ge=0, le=600)
    experience_max_months: int | None = Field(default=None, ge=0, le=600)
    ctc_min: int | None = Field(default=None, ge=0)
    ctc_max: int | None = Field(default=None, ge=0)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    required_skills: SkillList = Field(default_factory=list)
    preferred_skills: SkillList = Field(default_factory=list)
    openings: int = Field(default=1, ge=1, le=10_000)
    deadline_at: AwareDatetime | None = None
    eligibility: EligibilityIn = Field(default_factory=EligibilityIn)
    pipeline: PipelineIn = Field(default_factory=PipelineIn)

    @model_validator(mode="after")
    def _consistent(self) -> "JobFields":
        if self.experience_max_months is not None and self.experience_max_months < self.experience_min_months:
            raise PydanticCustomError("INVALID_RANGE", "The maximum experience is below the minimum")
        if self.ctc_min is not None and self.ctc_max is not None and self.ctc_max < self.ctc_min:
            raise PydanticCustomError("INVALID_RANGE", "The maximum pay is below the minimum")
        if self.location_type != LocationType.REMOTE and not self.locations:
            raise PydanticCustomError("REQUIRED", "Give at least one location (or make the job remote)")
        return self


class JobCreate(JobFields):
    pass


class JobUpdate(RequestSchema):
    """Any subset of the job's fields. A job that is pending approval cannot be edited (withdraw the submission first)."""

    title: text(160, min_length=3) | None = None  # type: ignore[valid-type]
    description: multiline_text(8_000) | None = None  # type: ignore[valid-type]
    employment_type: EmploymentType | None = None
    location_type: LocationType | None = None
    locations: Annotated[list[text(80)], Field(max_length=10)] | None = None  # type: ignore[valid-type]
    experience_min_months: int | None = Field(default=None, ge=0, le=600)
    experience_max_months: int | None = Field(default=None, ge=0, le=600)
    ctc_min: int | None = Field(default=None, ge=0)
    ctc_max: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    required_skills: SkillList | None = None
    preferred_skills: SkillList | None = None
    openings: int | None = Field(default=None, ge=1, le=10_000)
    deadline_at: AwareDatetime | None = None
    eligibility: EligibilityIn | None = None
    pipeline: PipelineIn | None = None


class ReasonRequest(RequestSchema):
    reason: text(200)  # type: ignore[valid-type]


class ReviewJobRequest(RequestSchema):
    approve: bool
    note: text(500) | None = Field(default=None, description="Required when rejecting: it is what the employer reads")  # type: ignore[valid-type]


# ---------------------------------------------------------------- responses
class MatchOut(ResponseSchema):
    score: int
    explanation: list[str]
    breakdown: dict[str, float]
    method: str


class EligibilityOut(ResponseSchema):
    eligible: bool
    reasons: list[str]


class JobOut(ResponseSchema):
    job_id: PublicIdOut
    employer_id: PublicIdOut
    company_name: str | None = None
    title: str
    description: str
    employment_type: str
    location_type: str
    locations: list[str]
    experience_min_months: int
    experience_max_months: int | None
    ctc_min: int | None
    ctc_max: int | None
    currency: str
    required_skills: list[str]
    preferred_skills: list[str]
    openings: int
    deadline_at: Timestamp | None
    visibility: str
    drive_id: PublicIdOut | None
    status: str
    published_at: Timestamp | None
    created_at: Timestamp


class EmployerJobOut(JobOut):
    """What the employer's own team (and a careers manager) sees: the full rules, the review note, the counts."""

    eligibility: dict[str, Any]
    institution_ids: list[str] = Field(default_factory=list)
    pipeline: dict[str, Any]
    review_note: str | None = None
    closed_reason: str | None = None
    applications: int = 0
    placed: int = 0
    created_by: PublicIdOut | None = None


class CandidateJobOut(JobOut):
    """A job as a student sees it: with whether they may apply and why not, and their match."""

    eligibility_result: EligibilityOut | None = None
    match: MatchOut | None = None
    applied: bool = False
    application_id: PublicIdOut | None = None


class EmployerJobResponse(SuccessResponse):
    job: EmployerJobOut


class EmployerJobPage(SuccessResponse):
    jobs: list[EmployerJobOut]
    page_context: PageContext


class CandidateJobResponse(SuccessResponse):
    job: CandidateJobOut


class CandidateJobPage(SuccessResponse):
    jobs: list[CandidateJobOut]
    page_context: PageContext
