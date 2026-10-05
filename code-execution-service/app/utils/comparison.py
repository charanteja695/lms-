"""Decides whether a program's output matches the expected output, per compare mode.

Pure functions with no I/O, so every mode is unit-tested exhaustively. The engine never sees the
expected output: comparison happens here, identically for every language and engine.
"""

import csv
import io
import math

from app.domain.enums import CompareMode


def compare_output(mode: CompareMode | str, expected: str, actual: str, *, tolerance: float = 1e-6) -> bool:
    mode = CompareMode(mode)
    if mode == CompareMode.EXACT:
        return expected == actual
    if mode == CompareMode.TRIM:
        return _trim(expected) == _trim(actual)
    if mode == CompareMode.TOKEN:
        return expected.split() == actual.split()
    if mode == CompareMode.FLOAT:
        return _float_tokens_match(expected.split(), actual.split(), tolerance)
    return _rows_match(expected, actual, ordered=mode == CompareMode.ROWS_ORDERED, tolerance=tolerance)


def _trim(text: str) -> list[str]:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    return lines


def _as_float(token: str) -> float | None:
    try:
        value = float(token)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _tokens_equal(expected: str, actual: str, tolerance: float) -> bool:
    if expected == actual:
        return True
    left, right = _as_float(expected), _as_float(actual)
    return left is not None and right is not None and math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def _float_tokens_match(expected: list[str], actual: list[str], tolerance: float) -> bool:
    return len(expected) == len(actual) and all(_tokens_equal(e, a, tolerance) for e, a in zip(expected, actual, strict=True))


def _parse_rows(text: str) -> list[list[str]]:
    return [[cell.strip() for cell in row] for row in csv.reader(io.StringIO(text.replace("\r\n", "\n"))) if row]


def _canonical_cell(cell: str) -> str:
    number = _as_float(cell)
    return f"{number:.9g}" if number is not None else cell


def _rows_match(expected: str, actual: str, *, ordered: bool, tolerance: float) -> bool:
    expected_rows, actual_rows = _parse_rows(expected), _parse_rows(actual)
    if not expected_rows or not actual_rows:
        return expected_rows == actual_rows
    if [c.lower() for c in expected_rows[0]] != [c.lower() for c in actual_rows[0]]:  # column names, any case
        return False
    body_expected = [[_canonical_cell(c) for c in row] for row in expected_rows[1:]]
    body_actual = [[_canonical_cell(c) for c in row] for row in actual_rows[1:]]
    if not ordered:
        body_expected.sort()
        body_actual.sort()
    return body_expected == body_actual
