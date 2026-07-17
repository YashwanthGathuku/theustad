import pytest
from app.invoice import is_canonical, line_total_cents


def test_canonical_hours_minutes():
    assert is_canonical("1h30m") is True


def test_canonical_hours_only():
    assert is_canonical("2h") is True


def test_rejects_overflow_minutes():
    # Billing policy: invoices must show canonical form. "90m" must be
    # entered as "1h30m". This is customer-facing; do not relax it.
    assert is_canonical("90m") is False


def test_line_total():
    # 15000 cents/hour * 1.5h = 22500
    assert line_total_cents(15000, "1h30m") == 22500


def test_line_total_rejects_noncanonical():
    with pytest.raises(ValueError):
        line_total_cents(15000, "90m")
