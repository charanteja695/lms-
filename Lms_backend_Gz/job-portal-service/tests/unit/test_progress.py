from datetime import UTC, datetime

from app.domain.enums import ApplicationStatus as S
from app.pipeline.machine import Template
from app.pipeline.progress import next_action, progress, stage_groups, steps

FULL = Template(assessment=True, ai_interview=True, hr_interview=True)
PLAIN = Template()


def states(status, template=FULL, **kw):
    return [(p["key"], p["state"]) for p in progress(status, template, **kw)]


def test_steps_follow_the_template():
    assert [s["key"] for s in steps(PLAIN)] == ["screening", "offer"]
    assert [s["label"] for s in steps(FULL)] == ["Resume check", "Online test", "AI interview", "HR round", "Offer"]


def test_progress_through_a_full_pipeline():
    assert states(S.APPLIED)[:2] == [("screening", "current"), ("assessment", "upcoming")]
    assert states(S.SHORTLISTED)[:2] == [("screening", "done"), ("assessment", "current")]
    assert states(S.ASSESSMENT_INVITED)[1] == ("assessment", "current")
    assert states(S.ASSESSMENT_COMPLETED)[1:3] == [("assessment", "done"), ("ai_interview", "current")]
    assert states(S.AI_INTERVIEW_COMPLETED)[2:4] == [("ai_interview", "done"), ("hr_interview", "current")]
    assert states(S.RECRUITER_REVIEW)[3] == ("hr_interview", "current")
    assert states(S.RECRUITER_REVIEW, PLAIN) == [("screening", "done"), ("offer", "current")]
    assert states(S.OFFERED)[-1] == ("offer", "current")
    assert all(state == "done" for _, state in states(S.PLACED)) and all(state == "done" for _, state in states(S.OFFER_ACCEPTED))


def test_a_closed_application_shows_where_it_stopped():
    assert states(S.REJECTED, stopped_from=S.AI_SCREENED)[0] == ("screening", "stopped")
    assert states(S.REJECTED, stopped_from=S.ASSESSMENT_COMPLETED)[1:3] == [("assessment", "done"), ("ai_interview", "stopped")]
    assert states(S.WITHDRAWN, stopped_from=S.HR_INTERVIEW)[3:] == [("hr_interview", "stopped"), ("offer", "upcoming")]
    assert states(S.OFFER_DECLINED)[-1] == ("offer", "stopped")


def test_next_action_only_when_the_candidate_must_act():
    expires = datetime(2026, 11, 1, tzinfo=UTC)
    offer = next_action(S.OFFERED, assessment_invite_state=None, offer_status="extended", offer_expires_at=expires)
    assert offer and offer.kind == "offer" and offer.due_at == expires
    assert next_action(S.OFFERED, assessment_invite_state=None, offer_status="accepted", offer_expires_at=None) is None
    assert next_action(S.ASSESSMENT_INVITED, assessment_invite_state="pending", offer_status=None, offer_expires_at=None) is None  # invite not delivered yet
    assert next_action(S.ASSESSMENT_INVITED, assessment_invite_state="sent", offer_status=None, offer_expires_at=None).kind == "assessment"  # type: ignore[union-attr]
    assert next_action(S.AI_INTERVIEW_INVITED, assessment_invite_state=None, offer_status=None, offer_expires_at=None).kind == "ai_interview"  # type: ignore[union-attr]
    assert next_action(S.RECRUITER_REVIEW, assessment_invite_state=None, offer_status=None, offer_expires_at=None) is None


def test_stage_groups_cover_every_status_once():
    from app.domain.enums import ApplicationStatus

    for template in (FULL, PLAIN):
        groups = stage_groups(template)
        held = [s for g in groups for s in g["statuses"]]
        assert len(held) == len(set(held))
        used = set(held)
        assert used <= {s.value for s in ApplicationStatus}
    assert [g["key"] for g in stage_groups(PLAIN)] == ["new", "shortlisted", "review", "offer", "closed"]
    assert [g["label"] for g in stage_groups(FULL)][2:5] == ["Online test", "AI interview", "HR round"]
