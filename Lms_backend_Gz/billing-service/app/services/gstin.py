"""Format check for a GSTIN (15 characters). It checks the shape only — a real GSTIN is verified against the GST portal, which this service
does not call."""

import re

_SHAPE = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def valid_gstin(value: str) -> bool:
    return bool(_SHAPE.fullmatch(value.strip().upper()))
