"""Live proctoring and exam reviews follow user-management's permission-matrix cells, one action at a time."""

from dataclasses import replace

from app.permissions.policy import can_appeal, can_monitor
from tests.conftest import make_claims

ORG = 1755000000008801


def test_watching_and_acting_on_a_session_are_separate_cells() -> None:
    viewer = replace(
        make_claims(user_id=1, role="staff", organization_id=ORG, scopes=("proctoring.view", "proctoring.monitor"), defaults=False), organization_type="institution"
    )
    assert can_monitor(viewer, student_organization_id=ORG, test_owner_id=None)
    assert not can_monitor(viewer, student_organization_id=ORG, test_owner_id=None, action="update")  # the coarse key no longer decides


def test_a_student_appeals_only_with_the_create_cell() -> None:
    assert can_appeal(make_claims(user_id=2, role="student", organization_id=ORG, scopes=()))
    assert not can_appeal(make_claims(user_id=2, role="student", organization_id=ORG, scopes=("exam_reviews.view", "proctoring.take"), defaults=False))
