"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import StrEnum


class EmployerStatus(StrEnum):
    """An employer's company profile is verified by a platform admin before any of its jobs can go live (docs/PRODUCT.md §5.7)."""

    DRAFT = "draft"  # being filled in
    PENDING = "pending"  # submitted for verification
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUSPENDED = "suspended"  # by an admin, or because the employer's account was suspended in user-management


class JobStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    INTERNSHIP = "internship"
    CONTRACT = "contract"


class LocationType(StrEnum):
    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"


class Visibility(StrEnum):
    PUBLIC = "public"  # every eligible student
    RESTRICTED = "restricted"  # only students of the listed institutions (a placement drive is a restricted job)


class ApplicationStatus(StrEnum):
    """applied → ai_screened → shortlisted | rejected → assessment → interview → review → offer → placed (docs/PRODUCT.md §5.7)."""

    APPLIED = "applied"
    AI_SCREENED = "ai_screened"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    ASSESSMENT_INVITED = "assessment_invited"
    ASSESSMENT_COMPLETED = "assessment_completed"
    AI_INTERVIEW_INVITED = "ai_interview_invited"
    AI_INTERVIEW_COMPLETED = "ai_interview_completed"
    RECRUITER_REVIEW = "recruiter_review"
    HR_INTERVIEW = "hr_interview"
    OFFERED = "offered"
    OFFER_ACCEPTED = "offer_accepted"
    OFFER_DECLINED = "offer_declined"
    PLACED = "placed"
    WITHDRAWN = "withdrawn"


TERMINAL_STATUSES = frozenset({ApplicationStatus.REJECTED, ApplicationStatus.OFFER_DECLINED, ApplicationStatus.PLACED, ApplicationStatus.WITHDRAWN})


class Actor(StrEnum):
    """Who moved an application. Only a human can reject (docs/PRODUCT.md §5.7: "the AI only recommends")."""

    CANDIDATE = "candidate"
    RECRUITER = "recruiter"
    SYSTEM = "system"  # this service reacting to an event or finishing its own work (never a rejection)


class OfferStatus(StrEnum):
    EXTENDED = "extended"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    WITHDRAWN = "withdrawn"


class DriveStatus(StrEnum):
    PROPOSED = "proposed"  # an institution's head invited the employer
    ACCEPTED = "accepted"  # the employer agreed; its jobs can be attached
    DECLINED = "declined"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class WorkKind(StrEnum):
    MATCH_JOB = "match_job"  # score every eligible candidate against one job
    MATCH_CANDIDATE = "match_candidate"  # score one candidate against every open job
    SCREEN = "screen"  # score a new application
    ASSESSMENT_INVITE = "assessment_invite"  # invite a shortlisted candidate to the job's hiring test


class WorkStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class DecisionKind(StrEnum):
    SCREENING = "screening"
    RANKING = "ranking"
