from lms_common.pagination import contains_pattern


def test_contains_pattern_escapes_wildcards() -> None:
    assert contains_pattern("50%_off") == r"%50\%\_off%"


def test_contains_pattern_wraps_plain_text() -> None:
    assert contains_pattern("reddy") == "%reddy%"
