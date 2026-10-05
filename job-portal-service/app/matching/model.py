"""The plain inputs of matching: what a job asks for and what a candidate has. Built from the database rows by the services; kept
free of them so the matching rules can be tested with a few lines of data."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class JobSpec:
    title: str
    description: str
    required_skills: tuple[str, ...]
    preferred_skills: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()
    location_type: str = "onsite"
    employment_type: str = "full_time"
    experience_min_months: int = 0
    experience_max_months: int | None = None
    ctc_max: int | None = None
    eligibility: dict[str, Any] = field(default_factory=dict)
    institution_ids: frozenset[int] = frozenset()
    restricted: bool = False

    @property
    def text(self) -> str:
        return f"{self.title}\n{', '.join(self.required_skills)}\n{', '.join(self.preferred_skills)}\n{self.description}"


@dataclass(frozen=True, slots=True)
class Candidate:
    """What a hiring decision may look at. No name, email, photo, date of birth, gender or institution *name* (the institution's id
    is kept only for the eligibility rule "open to selected institutions")."""

    user_id: int
    organization_id: int | None
    skills: tuple[str, ...] = ()
    technologies: tuple[str, ...] = ()
    job_titles: tuple[str, ...] = ()
    experience_months: int = 0
    graduation_year: int | None = None
    certificate_course_ids: frozenset[int] = frozenset()
    scores: dict[int, float] = field(default_factory=dict)  # course id -> best percent
    education: tuple[str, ...] = ()
    location: str | None = None
    target_roles: tuple[str, ...] = ()
    headline: str | None = None

    @property
    def text(self) -> str:
        """The profile as text, for the semantic component: skills, technologies, role titles and education — nothing personal."""
        parts = [self.headline or "", ", ".join(self.skills), ", ".join(self.technologies), ", ".join(self.job_titles), ", ".join(self.education), ", ".join(self.target_roles)]
        return "\n".join(p for p in parts if p)


@dataclass(frozen=True, slots=True)
class Preferences:
    locations: tuple[str, ...] = ()
    open_to_remote: bool = True
    roles: tuple[str, ...] = ()
    min_ctc: int | None = None
    employment_types: tuple[str, ...] = ()
    open_to_work: bool = True


@dataclass(frozen=True, slots=True)
class MatchResult:
    score: int
    breakdown: dict[str, float]
    explanation: list[str]
    semantic_method: str
    semantic_similarity: float


@dataclass(frozen=True, slots=True)
class Eligibility:
    eligible: bool
    reasons: list[str]  # why not — shown to the student ("what do I need?")
