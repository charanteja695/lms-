import pytest

from app.domain.enums import CompareMode
from app.utils.comparison import compare_output


@pytest.mark.parametrize(
    ("mode", "expected", "actual", "same"),
    [
        (CompareMode.EXACT, "3\n", "3\n", True),
        (CompareMode.EXACT, "3\n", "3", False),  # the final newline matters in exact mode
        (CompareMode.EXACT, "3 \n", "3\n", False),
        (CompareMode.TRIM, "3\n", "3", True),  # trailing blank lines and trailing spaces are ignored
        (CompareMode.TRIM, "1 2  \n3\n\n\n", "1 2\n3", True),
        (CompareMode.TRIM, "a\r\nb\r\n", "a\nb\n", True),  # Windows line endings
        (CompareMode.TRIM, "1 2\n", "1  2\n", False),  # but inner spacing counts
        (CompareMode.TRIM, "a\n\nb", "a\nb", False),  # and so do blank lines in the middle
        (CompareMode.TOKEN, "1 2\n3", "1\n2 3", True),  # any whitespace layout
        (CompareMode.TOKEN, "1 2 3", "1 2", False),
        (CompareMode.FLOAT, "3.14159 2", "3.1415899 2.0", True),
        (CompareMode.FLOAT, "1.0", "1.1", False),
        (CompareMode.FLOAT, "YES 1.5", "YES 1.5000001", True),
        (CompareMode.FLOAT, "YES 1.5", "NO 1.5", False),  # non-numeric tokens must match exactly
        (CompareMode.FLOAT, "nan", "nan", True),
        (CompareMode.FLOAT, "1", "1 2", False),
    ],
)
def test_text_modes(mode: CompareMode, expected: str, actual: str, same: bool) -> None:
    assert compare_output(mode, expected, actual, tolerance=1e-4) is same


def test_float_tolerance_is_configurable() -> None:
    assert compare_output(CompareMode.FLOAT, "1.0", "1.05", tolerance=0.1)
    assert not compare_output(CompareMode.FLOAT, "1.0", "1.05", tolerance=0.01)


@pytest.mark.parametrize(
    ("mode", "expected", "actual", "same"),
    [
        (CompareMode.ROWS_ORDERED, "id,name\n1,Asha\n2,Ravi\n", "id,name\n1,Asha\n2,Ravi\n", True),
        (CompareMode.ROWS_ORDERED, "id,name\n1,Asha\n2,Ravi\n", "id,name\n2,Ravi\n1,Asha\n", False),
        (CompareMode.ROWS_UNORDERED, "id,name\n1,Asha\n2,Ravi\n", "id,name\n2,Ravi\n1,Asha\n", True),
        (CompareMode.ROWS_UNORDERED, "id,name\n1,Asha\n", "id,name\n1,Asha\n1,Asha\n", False),  # duplicates count
        (CompareMode.ROWS_ORDERED, "ID,Name\n1,Asha\n", "id,name\n1,Asha\n", True),  # column names: any case
        (CompareMode.ROWS_ORDERED, "id,name\n1,Asha\n", "id,title\n1,Asha\n", False),  # but the names must match
        (CompareMode.ROWS_ORDERED, "n\n1\n", "n\n1.0\n", True),  # 1 and 1.0 are the same number
        (CompareMode.ROWS_ORDERED, "n\n1.5\n", "n\n1.50000000001\n", True),
        (CompareMode.ROWS_ORDERED, "v\nNULL\n", "v\nNULL\n", True),
        (CompareMode.ROWS_ORDERED, "v\n\"a,b\"\n", "v\n\"a,b\"\n", True),  # quoted commas
        (CompareMode.ROWS_ORDERED, "id\n1\n", "id\n1\n2\n", False),
        (CompareMode.ROWS_ORDERED, "", "", True),
        (CompareMode.ROWS_ORDERED, "id\n1\n", "", False),
    ],
)
def test_row_modes(mode: CompareMode, expected: str, actual: str, same: bool) -> None:
    assert compare_output(mode, expected, actual) is same
