"""The hiring pipeline as a state machine (docs/PRODUCT.md §5.7). Pure: no database, so every rule is testable on its own.

    applied → ai_screened → shortlisted | rejected
            → assessment_invited → assessment_completed
            → ai_interview_invited → ai_interview_completed
            → recruiter_review → hr_interview (optional) → offered → offer_accepted | offer_declined → placed
    withdrawn is possible at any stage

A job's *pipeline template* says which optional stages it uses (an assessment, an AI interview, an HR interview); a stage the
template turns on cannot be skipped, and one it leaves off cannot be entered. Three rules hold whatever the template says:

  * Only a **person** can reject. The system (which is what runs the AI screening) is never allowed to.
  * Only the **candidate** answers an offer or withdraws.
  * Only the **system** records that an assessment or an interview was completed: those facts come from events, not from clicks.
"""

from dataclasses import dataclass

from app.domain.enums import TERMINAL_STATUSES, Actor
from app.domain.enums import ApplicationStatus as S


@dataclass(frozen=True, slots=True)
class Template:
    """The optional stages a job uses."""

    assessment: bool = False
    ai_interview: bool = False
    hr_interview: bool = False


class TransitionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _after_shortlist(t: Template) -> S:
    return S.ASSESSMENT_INVITED if t.assessment else S.AI_INTERVIEW_INVITED if t.ai_interview else S.RECRUITER_REVIEW


def _after_assessment(t: Template) -> S:
    return S.AI_INTERVIEW_INVITED if t.ai_interview else S.RECRUITER_REVIEW


def allowed_next(status: S, template: Template, actor: Actor) -> set[S]:
    """The statuses ``actor`` may move an application in ``status`` to."""
    if status in TERMINAL_STATUSES:
        return set()
    nexts: dict[Actor, set[S]] = {Actor.CANDIDATE: set(), Actor.RECRUITER: set(), Actor.SYSTEM: set()}
    if status in {S.APPLIED}:
        nexts[Actor.SYSTEM].add(S.AI_SCREENED)
        nexts[Actor.RECRUITER] |= {S.SHORTLISTED, S.REJECTED}
    elif status == S.AI_SCREENED:
        nexts[Actor.RECRUITER] |= {S.SHORTLISTED, S.REJECTED}
    elif status == S.SHORTLISTED:
        nexts[Actor.RECRUITER] |= {_after_shortlist(template), S.REJECTED}
    elif status == S.ASSESSMENT_INVITED:
        nexts[Actor.SYSTEM].add(S.ASSESSMENT_COMPLETED)
        nexts[Actor.RECRUITER].add(S.REJECTED)
    elif status == S.ASSESSMENT_COMPLETED:
        nexts[Actor.RECRUITER] |= {_after_assessment(template), S.REJECTED}
    elif status == S.AI_INTERVIEW_INVITED:
        nexts[Actor.SYSTEM].add(S.AI_INTERVIEW_COMPLETED)
        nexts[Actor.RECRUITER].add(S.REJECTED)
    elif status == S.AI_INTERVIEW_COMPLETED:
        nexts[Actor.RECRUITER] |= {S.RECRUITER_REVIEW, S.REJECTED}
    elif status == S.RECRUITER_REVIEW:
        nexts[Actor.RECRUITER] |= {S.HR_INTERVIEW if template.hr_interview else S.OFFERED, S.REJECTED}
    elif status == S.HR_INTERVIEW:
        nexts[Actor.RECRUITER] |= {S.OFFERED, S.REJECTED}
    elif status == S.OFFERED:
        nexts[Actor.CANDIDATE] |= {S.OFFER_ACCEPTED, S.OFFER_DECLINED}
        nexts[Actor.SYSTEM].add(S.OFFER_DECLINED)  # the offer expired unanswered
        nexts[Actor.RECRUITER].add(S.REJECTED)  # an offer withdrawn before it was answered
    elif status == S.OFFER_ACCEPTED:
        nexts[Actor.RECRUITER].add(S.PLACED)
    nexts[Actor.CANDIDATE].add(S.WITHDRAWN)
    return nexts[actor]


def check(status: S, to: S, template: Template, actor: Actor) -> None:
    """Raise ``TransitionError`` unless ``actor`` may move an application from ``status`` to ``to``."""
    if status in TERMINAL_STATUSES:
        raise TransitionError("APPLICATION_CLOSED", f"This application is already {status.value}.")
    if to in allowed_next(status, template, actor):
        return
    if to == S.REJECTED and actor == Actor.SYSTEM:
        raise TransitionError("AI_CANNOT_REJECT", "Only a person can reject an application.")
    if to in {S.OFFER_ACCEPTED, S.OFFER_DECLINED} and actor != Actor.CANDIDATE and not (actor == Actor.SYSTEM and to == S.OFFER_DECLINED):
        raise TransitionError("CANDIDATE_ONLY", "Only the candidate answers an offer.")
    if to == S.WITHDRAWN:
        raise TransitionError("CANDIDATE_ONLY", "Only the candidate can withdraw.")
    if to in {S.ASSESSMENT_COMPLETED, S.AI_INTERVIEW_COMPLETED, S.AI_SCREENED} and actor != Actor.SYSTEM:
        raise TransitionError("SYSTEM_ONLY", f"{to.value} is recorded by the platform, not chosen.")
    raise TransitionError("INVALID_TRANSITION", f"An application that is {status.value} cannot move to {to.value} here.")


def default_next(status: S, template: Template) -> S | None:
    """Where 'advance' takes a recruiter from ``status`` (None when the next step is a choice or not theirs to make)."""
    if status in {S.APPLIED, S.AI_SCREENED}:
        return S.SHORTLISTED
    if status == S.SHORTLISTED:
        return _after_shortlist(template)
    if status == S.ASSESSMENT_COMPLETED:
        return _after_assessment(template)
    if status == S.AI_INTERVIEW_COMPLETED:
        return S.RECRUITER_REVIEW
    if status == S.RECRUITER_REVIEW:
        return S.HR_INTERVIEW if template.hr_interview else S.OFFERED
    if status == S.HR_INTERVIEW:
        return S.OFFERED
    if status == S.OFFER_ACCEPTED:
        return S.PLACED
    return None
