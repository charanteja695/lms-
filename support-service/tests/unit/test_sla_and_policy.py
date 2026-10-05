from datetime import datetime, timedelta

from app.core.security import AccessTokenClaims
from app.domain.enums import QUEUE_FOR_CATEGORY, Category, Queue
from app.models.ticket import Ticket
from app.permissions import policy
from app.sla import Targets, due_at, is_breached, minutes_between, paused_total, targets_for
from tests.conftest import EXAM_TEAM, ORG_A, ORG_B, STAFF_A, STUDENT, SUPPORT, make_claims

T0 = datetime(2026, 9, 1, 9, 0, 0)


def test_defaults_and_overrides():
    assert targets_for("platform_support", "urgent", {}) == Targets(30, 240)
    assert targets_for("platform_support", "urgent", {("platform_support", "urgent"): Targets(5, 60)}) == Targets(5, 60)
    assert targets_for("exam_team", "urgent", {("platform_support", "urgent"): Targets(5, 60)}) == Targets(30, 240)


def test_due_time_moves_out_by_the_paused_time():
    assert due_at(T0, 60, 0) == T0 + timedelta(hours=1)
    assert due_at(T0, 60, 600) == T0 + timedelta(minutes=70)


def test_paused_total_adds_the_running_pause_only():
    assert paused_total(100, None, T0) == 100
    assert paused_total(100, T0 - timedelta(seconds=50), T0) == 150
    assert paused_total(0, T0 + timedelta(seconds=5), T0) == 0  # clock skew never subtracts


def test_a_paused_or_untargeted_clock_cannot_breach():
    due = T0 + timedelta(minutes=10)
    assert is_breached(T0 + timedelta(minutes=11), due, paused=False)
    assert not is_breached(T0 + timedelta(minutes=11), due, paused=True)
    assert not is_breached(T0 + timedelta(minutes=9), due, paused=False)
    assert not is_breached(T0, None, paused=False)


def test_minutes_between():
    assert minutes_between(T0, T0 + timedelta(seconds=90)) == 1.5
    assert minutes_between(None, T0) is None


def test_every_category_has_a_queue():
    assert set(QUEUE_FOR_CATEGORY) == set(Category)
    assert QUEUE_FOR_CATEGORY[Category.INTEGRITY] == Queue.EXAM_TEAM


def _ticket(queue: str, org: int | None = ORG_A) -> Ticket:
    return Ticket(queue=queue, organization_id=org, requester_user_id=STUDENT)


def _claims(user_id: int, role: str, org: int | None, *scopes: str) -> AccessTokenClaims:
    return make_claims(user_id=user_id, role=role, organization_id=org, scopes=scopes)


def test_handling_rules():
    manager = _claims(SUPPORT, "admin", None, "support.manage")
    exam = _claims(EXAM_TEAM, "admin", None, "exams.manage")
    staff_a = _claims(STAFF_A, "staff", ORG_A)
    staff_b = _claims(STAFF_A, "staff", ORG_B)
    student = _claims(STUDENT, "student", ORG_A)
    for queue in Queue:
        assert policy.can_handle(manager, _ticket(queue))
    assert policy.can_handle(exam, _ticket("exam_team")) and not policy.can_handle(exam, _ticket("platform_support"))
    assert policy.can_handle(staff_a, _ticket("batch_staff")) and not policy.can_handle(staff_b, _ticket("batch_staff"))
    assert not policy.can_handle(staff_a, _ticket("platform_support"))
    assert not policy.can_handle(student, _ticket("batch_staff"))
    assert policy.can_view(student, _ticket("batch_staff")) and not policy.can_view(_claims(STUDENT + 1, "student", ORG_A), _ticket("batch_staff"))
    assert not policy.is_agent(student)


def test_who_may_assign_others():
    head = _claims(1, "institution_head", ORG_A)
    assert policy.can_assign_others(head, _ticket("batch_staff"))
    assert not policy.can_assign_others(head, _ticket("batch_staff", ORG_B))
    assert not policy.can_assign_others(head, _ticket("platform_support"))
    assert not policy.can_assign_others(_claims(2, "staff", ORG_A), _ticket("batch_staff"))
    assert policy.can_assign_others(_claims(3, "super_admin", None), _ticket("exam_team"))
