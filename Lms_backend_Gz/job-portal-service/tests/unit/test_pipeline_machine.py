import pytest

from app.domain.enums import TERMINAL_STATUSES, Actor
from app.domain.enums import ApplicationStatus as S
from app.pipeline.machine import Template, TransitionError, allowed_next, check, default_next

PLAIN = Template()
FULL = Template(assessment=True, ai_interview=True, hr_interview=True)


def path(template: Template) -> list[S]:
    """The happy path a recruiter walks with 'advance', with the system's steps in between."""
    steps, status = [S.APPLIED], S.APPLIED
    while status != S.PLACED:
        if status == S.APPLIED:
            status = S.AI_SCREENED
        elif status == S.ASSESSMENT_INVITED:
            status = S.ASSESSMENT_COMPLETED
        elif status == S.AI_INTERVIEW_INVITED:
            status = S.AI_INTERVIEW_COMPLETED
        elif status == S.OFFERED:
            status = S.OFFER_ACCEPTED
        else:
            nxt = default_next(status, template)
            assert nxt is not None, status
            status = nxt
        steps.append(status)
    return steps


def test_the_plain_pipeline_goes_straight_to_review_and_offer():
    assert path(PLAIN) == [S.APPLIED, S.AI_SCREENED, S.SHORTLISTED, S.RECRUITER_REVIEW, S.OFFERED, S.OFFER_ACCEPTED, S.PLACED]


def test_a_full_template_cannot_be_skipped():
    assert path(FULL) == [
        S.APPLIED, S.AI_SCREENED, S.SHORTLISTED, S.ASSESSMENT_INVITED, S.ASSESSMENT_COMPLETED, S.AI_INTERVIEW_INVITED, S.AI_INTERVIEW_COMPLETED, S.RECRUITER_REVIEW, S.HR_INTERVIEW,
        S.OFFERED, S.OFFER_ACCEPTED, S.PLACED,
    ]
    assert S.RECRUITER_REVIEW not in allowed_next(S.SHORTLISTED, FULL, Actor.RECRUITER)  # the assessment is required
    assert S.OFFERED not in allowed_next(S.RECRUITER_REVIEW, FULL, Actor.RECRUITER)  # so is the HR interview
    assert S.ASSESSMENT_INVITED not in allowed_next(S.SHORTLISTED, PLAIN, Actor.RECRUITER)  # a stage the job does not use cannot be entered


def test_an_interview_only_template_skips_the_assessment():
    template = Template(ai_interview=True)
    assert default_next(S.SHORTLISTED, template) == S.AI_INTERVIEW_INVITED and default_next(S.ASSESSMENT_COMPLETED, Template(assessment=True)) == S.RECRUITER_REVIEW


@pytest.mark.parametrize("status", [S.APPLIED, S.AI_SCREENED, S.SHORTLISTED, S.ASSESSMENT_INVITED, S.ASSESSMENT_COMPLETED, S.AI_INTERVIEW_INVITED, S.AI_INTERVIEW_COMPLETED, S.RECRUITER_REVIEW, S.HR_INTERVIEW, S.OFFERED])
def test_the_system_can_never_reject(status):
    assert S.REJECTED not in allowed_next(status, FULL, Actor.SYSTEM)
    with pytest.raises(TransitionError) as caught:
        check(status, S.REJECTED, FULL, Actor.SYSTEM)
    assert caught.value.code == "AI_CANNOT_REJECT"


@pytest.mark.parametrize("status", [S.APPLIED, S.AI_SCREENED, S.SHORTLISTED, S.ASSESSMENT_INVITED, S.ASSESSMENT_COMPLETED, S.AI_INTERVIEW_INVITED, S.AI_INTERVIEW_COMPLETED, S.RECRUITER_REVIEW, S.HR_INTERVIEW, S.OFFERED])
def test_a_person_can_reject_at_any_open_stage(status):
    check(status, S.REJECTED, FULL, Actor.RECRUITER)


def test_terminal_applications_never_move():
    for status in TERMINAL_STATUSES:
        for actor in Actor:
            assert allowed_next(status, FULL, actor) == set()
        with pytest.raises(TransitionError) as caught:
            check(status, S.SHORTLISTED, FULL, Actor.RECRUITER)
        assert caught.value.code == "APPLICATION_CLOSED"


def test_only_the_candidate_answers_an_offer_or_withdraws():
    assert allowed_next(S.OFFERED, FULL, Actor.CANDIDATE) == {S.OFFER_ACCEPTED, S.OFFER_DECLINED, S.WITHDRAWN}
    assert allowed_next(S.OFFERED, FULL, Actor.SYSTEM) == {S.OFFER_DECLINED}  # an offer that expired
    for actor in (Actor.RECRUITER, Actor.SYSTEM):
        with pytest.raises(TransitionError) as caught:
            check(S.OFFERED, S.OFFER_ACCEPTED, FULL, actor)
        assert caught.value.code == "CANDIDATE_ONLY"
        with pytest.raises(TransitionError) as withdrawn:
            check(S.SHORTLISTED, S.WITHDRAWN, FULL, actor)
        assert withdrawn.value.code == "CANDIDATE_ONLY"
    for status in (S.APPLIED, S.SHORTLISTED, S.ASSESSMENT_INVITED, S.HR_INTERVIEW, S.OFFER_ACCEPTED):
        assert S.WITHDRAWN in allowed_next(status, FULL, Actor.CANDIDATE)  # at any stage


def test_completion_facts_come_from_events_not_clicks():
    for target in (S.ASSESSMENT_COMPLETED, S.AI_INTERVIEW_COMPLETED):
        with pytest.raises(TransitionError) as caught:
            check(S.ASSESSMENT_INVITED if target == S.ASSESSMENT_COMPLETED else S.AI_INTERVIEW_INVITED, target, FULL, Actor.RECRUITER)
        assert caught.value.code == "SYSTEM_ONLY"
    check(S.ASSESSMENT_INVITED, S.ASSESSMENT_COMPLETED, FULL, Actor.SYSTEM)
    check(S.APPLIED, S.AI_SCREENED, FULL, Actor.SYSTEM)
    with pytest.raises(TransitionError) as screened:
        check(S.APPLIED, S.AI_SCREENED, FULL, Actor.RECRUITER)
    assert screened.value.code == "SYSTEM_ONLY"


def test_invalid_moves_are_named_as_such():
    with pytest.raises(TransitionError) as caught:
        check(S.APPLIED, S.OFFERED, FULL, Actor.RECRUITER)
    assert caught.value.code == "INVALID_TRANSITION"
    assert default_next(S.OFFERED, FULL) is None and default_next(S.ASSESSMENT_INVITED, FULL) is None
