"""Jobs and placements follow user-management's permission-matrix cells, one action at a time."""

from dataclasses import replace

from app.permissions.policy import is_institution_head, is_institution_staff, is_student
from tests.conftest import make_claims

ORG = 1755000000060901


def test_a_student_left_view_only_can_browse_but_not_apply_or_withdraw() -> None:
    browser = make_claims(user_id=1, role="student", organization_id=ORG, scopes=("jobs.view", "jobs.apply"), defaults=False)
    assert is_student(browser) and not is_student(browser, "create") and not is_student(browser, "revoke")
    assert not is_student(make_claims(user_id=2, role="super_admin", organization_id=None))  # never a candidate


def test_proposing_a_drive_is_its_own_cell() -> None:
    head = replace(make_claims(user_id=3, role="institution_head", organization_id=ORG, scopes=("placements.view", "jobs.placements", "jobs.drives.propose"), defaults=False), organization_type="institution")
    assert is_institution_staff(head) and not is_institution_head(head)  # the coarse jobs.drives.propose key no longer decides
