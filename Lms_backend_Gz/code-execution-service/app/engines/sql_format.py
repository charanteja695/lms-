"""The canonical text form of a SQL result set: a header row of column names then one CSV row per record.

Authors write a SQL problem's expected output in this form, and the ``rows_*`` compare modes parse it
back (app/utils/comparison.py). NULL is written as ``NULL`` so it cannot be confused with an empty string.
"""

import csv
import io
from collections.abc import Sequence
from typing import Any


def _cell(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, bytes | bytearray | memoryview):
        return "0x" + bytes(value).hex()
    return str(value)


def format_result(columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    if not columns:
        return ""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_cell(value) for value in row])
    return buffer.getvalue()
