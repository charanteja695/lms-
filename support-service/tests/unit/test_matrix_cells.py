"""Help tickets and the support queue follow user-management's permission-matrix cells, one action at a time."""

from app.permissions.policy import is_institution_staff, is_student
from tests.conftest import make_claims

ORG = 1755000000080901


def test_reading_and_acting_are_separate_cells() -> None:
    student = make_claims(user_id=1, role="student", organization_id=ORG, scopes=("support.view", "support.ask"), defaults=False)
    assert is_student(student) and not is_student(student, "create")
    reader = make_claims(user_id=2, role="staff", organization_id=ORG, scopes=("support_queue.view", "support.agent"), defaults=False)
    assert is_institution_staff(reader) and not is_institution_staff(reader, "update")  # the coarse support.agent key no longer decides
