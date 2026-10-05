"""The arithmetic of an invoice: integer paise throughout, so the parts always add up to the total."""

from datetime import date

import pytest

from app.billing import tax
from app.services.gstin import valid_gstin


def test_the_financial_year_runs_april_to_march():
    assert tax.financial_year(date(2026, 3, 31)) == "2025-26"
    assert tax.financial_year(date(2026, 4, 1)) == "2026-27"
    assert tax.financial_year(date(2026, 12, 31)) == "2026-27"
    assert tax.financial_year(date(2027, 3, 31)) == "2026-27"
    assert tax.financial_year(date(2099, 6, 1)) == "2099-00"


def test_prorate_is_seats_times_price_times_term_over_a_year_rounded_half_up():
    assert tax.prorate(1_000_000, 100, 365) == 100_000_000
    assert tax.prorate(1_000_000, 100, 730) == 200_000_000
    assert tax.prorate(1, 1, 183) == 1  # 183/365 = 0.501: rounds up
    assert tax.prorate(1, 1, 182) == 0  # 182/365 = 0.4986: rounds down


@pytest.mark.parametrize(("taxable", "cgst", "sgst", "igst"), [(1000, 90, 90, 0), (1005, 91, 90, 0), (0, 0, 0, 0)])
def test_an_in_state_sale_splits_the_gst_in_two_and_the_odd_paisa_goes_to_cgst(taxable, cgst, sgst, igst):
    assert tax.gst(taxable, 18, intra_state=True) == (cgst, sgst, igst)


def test_any_other_sale_is_all_igst():
    assert tax.gst(1000, 18, intra_state=False) == (0, 0, 180)


def test_the_parts_of_the_tax_always_add_up_to_the_tax():
    for taxable in range(0, 5000, 7):
        cgst, sgst, igst = tax.gst(taxable, 18, intra_state=True)
        assert cgst + sgst + igst == (taxable * 18 + 50) // 100


def test_states_compare_ignoring_case_and_spacing():
    assert tax.same_state("Karnataka", "  karnataka ")
    assert tax.same_state("Tamil Nadu", "TAMIL   NADU")
    assert not tax.same_state("Karnataka", "Kerala")


def test_a_discount_never_takes_an_invoice_below_zero():
    assert tax.after_discount(1000, 300) == (300, 700)
    assert tax.after_discount(1000, 5000) == (1000, 0)
    assert tax.after_discount(1000, -5) == (0, 1000)


def test_a_gstin_is_checked_for_shape():
    assert valid_gstin("29ABCDE1234F1Z5")
    assert valid_gstin(" 29abcde1234f1z5 ")
    assert not valid_gstin("29ABCDE1234F1Z")  # too short
    assert not valid_gstin("ABABCDE1234F1Z5")  # the state code is digits
    assert not valid_gstin("29ABCDE1234F1X5")  # position 14 is always Z
