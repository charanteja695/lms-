import pytest

from app.core.exceptions import ValidationFailedError
from app.guardrails.tools import check_tools_allowed


def test_allows_a_tool_on_the_allow_list() -> None:
    check_tools_allowed([{"name": "lookup_enrolment_status"}], ["lookup_enrolment_status", "lookup_attempt_status"])


def test_allows_no_tools_at_all() -> None:
    check_tools_allowed([], [])


def test_rejects_a_tool_not_on_the_allow_list() -> None:
    with pytest.raises(ValidationFailedError) as excinfo:
        check_tools_allowed([{"name": "delete_account"}], ["lookup_enrolment_status"])
    assert excinfo.value.code == "TOOL_NOT_ALLOWED"
    assert excinfo.value.details[0]["message"] == "delete_account"


def test_rejects_when_any_one_of_several_tools_is_disallowed() -> None:
    with pytest.raises(ValidationFailedError):
        check_tools_allowed([{"name": "lookup_enrolment_status"}, {"name": "delete_account"}], ["lookup_enrolment_status"])
