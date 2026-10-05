"""Enums stored as plain strings (not native DB enums) so new values don't need a type migration."""

from enum import StrEnum


class PlanKind(StrEnum):
    MOCK = "mock"  # a student's practice, feedback and an improvement plan
    SCREENING = "screening"  # a hiring-pipeline stage, scored for the recruiter


class PlanStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"  # immutable: to change it, make a new version
    RETIRED = "retired"


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    SENIOR = "senior"


class RoundType(StrEnum):
    INTRO = "intro"
    TECHNICAL = "technical"  # technical Q&A
    CODING = "coding"  # live coding in the compiler
    SYSTEM_DESIGN = "system_design"  # senior roles
    BEHAVIOURAL = "behavioural"


class Criterion(StrEnum):
    """The rubric (docs/PRODUCT.md §5.8): what every round is scored on."""

    TECHNICAL_DEPTH = "technical_depth"
    PROBLEM_SOLVING = "problem_solving"
    CODE_QUALITY = "code_quality"
    COMMUNICATION = "communication"
    BEHAVIOURAL = "behavioural"  # culture / behavioural


class InterviewStatus(StrEnum):
    INVITED = "invited"  # waiting for the candidate to consent and start
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"  # the conversation is over; waiting for the evaluation
    EVALUATED = "evaluated"  # rubric scores and a recommendation exist
    REVIEWED = "reviewed"  # a person has confirmed or overridden the recommendation
    EXPIRED = "expired"  # never started in time
    CANCELLED = "cancelled"


class Speaker(StrEnum):
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"
    SYSTEM = "system"


class TurnKind(StrEnum):
    QUESTION = "question"
    FOLLOW_UP = "follow_up"
    ANSWER = "answer"
    CODE = "code"  # code the candidate ran in the coding round
    CODE_RESULT = "code_result"  # what the compiler said
    NOTE = "note"  # a system note: round change, time warning


class Recommendation(StrEnum):
    STRONG_YES = "strong_yes"
    YES = "yes"
    LEAN_NO = "lean_no"
    NO = "no"


class EvaluationStatus(StrEnum):
    PENDING = "pending"
    FINAL = "final"
    FAILED = "failed"


class AppealStatus(StrEnum):
    OPEN = "open"
    UPHELD = "upheld"  # the candidate is granted a retake
    DENIED = "denied"


class WorkKind(StrEnum):
    EVALUATE = "evaluate"  # score a finished interview
    CREATE_SCREENING = "create_screening"  # invite a candidate the pipeline has sent here
    CLOSE_STALE = "close_stale"  # end interviews whose time ran out, expire unstarted invitations


class WorkStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


DEFAULT_CRITERIA = tuple(c.value for c in Criterion)
