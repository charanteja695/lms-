"""The arithmetic of an invoice (docs/PRODUCT.md §5.10). Pure integer functions over paise: nothing here touches a float, so the
parts of an invoice always add up to its total exactly."""

from datetime import date


def financial_year(day: date) -> str:
    """India's financial year runs April–March: 2026-09-28 is in "2026-27", 2027-02-01 is too."""
    start = day.year if day.month >= 4 else day.year - 1
    return f"{start}-{(start + 1) % 100:02d}"


def prorate(unit_amount: int, seats: int, term_days: int) -> int:
    """seats × a per-365-days price × the term, rounded half up to the paisa."""
    return (seats * unit_amount * term_days + 182) // 365


def normalise_state(state: str) -> str:
    return " ".join(state.casefold().split())


def same_state(seller: str, customer: str) -> bool:
    return normalise_state(seller) == normalise_state(customer)


def gst(taxable: int, rate_percent: int, *, intra_state: bool) -> tuple[int, int, int]:
    """(cgst, sgst, igst). One rate; an in-state sale splits it in two halves (the odd paisa goes to CGST), any other sale is all IGST."""
    total = (taxable * rate_percent + 50) // 100
    if intra_state:
        cgst = (total + 1) // 2
        return cgst, total - cgst, 0
    return 0, 0, total


def after_discount(subtotal: int, discount: int) -> tuple[int, int]:
    """(discount actually applied, taxable amount): a discount can bring an invoice to zero but never below."""
    applied = max(0, min(discount, subtotal))
    return applied, subtotal - applied

