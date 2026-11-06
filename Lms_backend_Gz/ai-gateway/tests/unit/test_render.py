import pytest

from app.prompt.render import MissingVariables, placeholders_in, render


def test_renders_a_simple_template() -> None:
    assert render("Hello {{name}}, welcome to {{course}}.", {"name": "Aarav", "course": "MERN"}) == "Hello Aarav, welcome to MERN."


def test_an_unused_supplied_variable_is_not_an_error() -> None:
    assert render("Hello {{name}}.", {"name": "Aarav", "extra": "ignored"}) == "Hello Aarav."


def test_a_missing_variable_raises_with_its_name() -> None:
    with pytest.raises(MissingVariables) as excinfo:
        render("Hello {{name}}, welcome to {{course}}.", {"name": "Aarav"})
    assert excinfo.value.names == ("course",)


def test_several_missing_variables_are_all_reported_sorted() -> None:
    with pytest.raises(MissingVariables) as excinfo:
        render("{{zebra}} {{apple}}", {})
    assert excinfo.value.names == ("apple", "zebra")


def test_single_braces_are_left_alone() -> None:
    """A template can still show JSON or code without every brace being read as a placeholder."""
    assert render('Example: {"key": "value"} and {{name}}', {"name": "Aarav"}) == 'Example: {"key": "value"} and Aarav'


def test_placeholders_in_finds_every_distinct_name() -> None:
    assert placeholders_in("{{a}} {{b}} {{a}}") == {"a", "b"}
