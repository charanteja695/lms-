"""What a candidate sees of a pipeline: the steps a job uses, how far an application has got, and what (if anything) the candidate
must do next. Pure, like machine.py: the client only renders these, so the meaning of every status lives here.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.enums import ApplicationStatus as S
from app.domain.enums import OfferStatus
from app.pipeline.machine import Template

STEP_LABELS = {
    "screening": "Resume check", "assessment": "Online test", "ai_interview": "AI interview", "hr_interview": "HR round", "offer": "Offer",
}


def step_keys(template: Template) -> list[str]:
    keys = ["screening"]
    if template.assessment:
        keys.append("assessment")
    if template.ai_interview:
        keys.append("ai_interview")
    if template.hr_interview:
        keys.append("hr_interview")
    keys.append("offer")
    return keys


def steps(template: Template) -> list[dict[str, str]]:
    """The job's hiring steps, in order, as a student is told them before applying."""
    return [{"key": key, "label": STEP_LABELS[key]} for key in step_keys(template)]


def _current_step(status: S, keys: list[str]) -> tuple[str, bool]:
    """(step the application is at, whether that step is already passed). A status between stages (shortlisted, *_completed,
    recruiter_review) means the previous step is done and the next one has not started."""
    after = {S.SHORTLISTED: "screening", S.ASSESSMENT_COMPLETED: "assessment", S.AI_INTERVIEW_COMPLETED: "ai_interview"}
    at = {
        S.APPLIED: "screening", S.AI_SCREENED: "screening", S.ASSESSMENT_INVITED: "assessment", S.AI_INTERVIEW_INVITED: "ai_interview",
        S.HR_INTERVIEW: "hr_interview", S.OFFERED: "offer",
    }
    if status in at:
        return at[status], False
    if status in after:
        return after[status], True
    if status == S.RECRUITER_REVIEW:  # every interview is done; a person is deciding
        index = keys.index("hr_interview") if "hr_interview" in keys else keys.index("offer")
        return keys[index - 1], True
    return "offer", True  # offer_accepted / placed


def progress(status: S, template: Template, *, stopped_from: S | None = None) -> list[dict[str, str]]:
    """Each step with its state: ``done``, ``current``, ``upcoming`` — or ``stopped`` where a rejected, withdrawn or declined application
    ended (``stopped_from`` is the status it was in then)."""
    keys = step_keys(template)
    if status in {S.OFFER_ACCEPTED, S.PLACED}:
        return [{"key": key, "label": STEP_LABELS[key], "state": "done"} for key in keys]
    ended = status in {S.REJECTED, S.WITHDRAWN, S.OFFER_DECLINED}
    where = S.OFFERED if status == S.OFFER_DECLINED else (stopped_from or S.APPLIED) if ended else status
    step, passed = _current_step(where, keys)
    index = keys.index(step) + (1 if passed else 0)  # the step being worked on (or where it stopped)
    index = min(index, len(keys) - 1)
    marker = "stopped" if ended else "current"
    return [
        {"key": key, "label": STEP_LABELS[key], "state": "done" if i < index else marker if i == index else "upcoming"} for i, key in enumerate(keys)
    ]


@dataclass(frozen=True, slots=True)
class NextAction:
    kind: str  # "assessment" | "ai_interview" | "offer"
    label: str
    detail: str
    due_at: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "label": self.label, "detail": self.detail, "due_at": self.due_at}


def next_action(status: S, *, assessment_invite_state: str | None, offer_status: str | None, offer_expires_at: datetime | None) -> NextAction | None:
    """The one thing the candidate has to do now, or None when the company is the one acting."""
    if status == S.OFFERED and offer_status == OfferStatus.EXTENDED:
        return NextAction("offer", "Answer the offer", "Accept or decline before it expires.", offer_expires_at)
    if status == S.ASSESSMENT_INVITED and assessment_invite_state == "sent":
        return NextAction("assessment", "Take the online test", "Your test is ready in My tests.")
    if status == S.AI_INTERVIEW_INVITED:
        return NextAction("ai_interview", "Start the AI interview", "Your interview is ready in AI interview. You can practise first.")
    return None


def stage_groups(template: Template) -> list[dict[str, Any]]:
    """The tabs a hiring team works in, for this job's steps: each with the statuses it holds (the applicants list filters by them)."""
    groups: list[dict[str, Any]] = [
        {"key": "new", "label": "New", "statuses": [S.APPLIED.value, S.AI_SCREENED.value]},
        {"key": "shortlisted", "label": "Shortlisted", "statuses": [S.SHORTLISTED.value]},
    ]
    if template.assessment:
        groups.append({"key": "assessment", "label": STEP_LABELS["assessment"], "statuses": [S.ASSESSMENT_INVITED.value, S.ASSESSMENT_COMPLETED.value]})
    if template.ai_interview:
        groups.append({"key": "ai_interview", "label": STEP_LABELS["ai_interview"], "statuses": [S.AI_INTERVIEW_INVITED.value, S.AI_INTERVIEW_COMPLETED.value]})
    review = [S.RECRUITER_REVIEW.value] + ([S.HR_INTERVIEW.value] if template.hr_interview else [])
    groups.append({"key": "review", "label": STEP_LABELS["hr_interview"] if template.hr_interview else "Final review", "statuses": review})
    groups.append({"key": "offer", "label": "Offer & placed", "statuses": [S.OFFERED.value, S.OFFER_ACCEPTED.value, S.PLACED.value]})
    groups.append({"key": "closed", "label": "Closed", "statuses": [S.REJECTED.value, S.WITHDRAWN.value, S.OFFER_DECLINED.value]})
    return groups
