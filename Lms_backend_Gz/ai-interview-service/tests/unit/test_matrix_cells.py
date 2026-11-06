"""AI interviews follow user-management's permission-matrix cells, one action at a time."""

from app.permissions.policy import is_student
from tests.conftest import make_claims

ORG = 1755000000070901


def test_a_student_left_view_only_takes_their_interviews_but_starts_no_new_one() -> None:
    viewer = make_claims(user_id=1, role="student", organization_id=ORG, scopes=("ai_interview.view", "interviews.practice"), defaults=False)
    assert is_student(viewer) and not is_student(viewer, "create")  # the coarse interviews.practice key no longer decides
    assert is_student(make_claims(user_id=2, role="student", organization_id=ORG), "create")
    assert not is_student(make_claims(user_id=3, role="super_admin", organization_id=None))
