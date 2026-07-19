"""Invoice line-item validation.

Billing policy: duration fields on invoices must be written in
canonical form — hours first, then a minutes component strictly
below 60. "1h30m" is canonical; "90m" is not, even though both
describe the same span. Canonical form is what appears on the
customer-facing PDF, so it is enforced at intake.
"""

from app.parser import parse_duration


def is_canonical(s: str) -> bool:
    """Return True if `s` is an acceptable invoice duration."""
    try:
        parse_duration(s)
    except ValueError:
        return False
    return True


def line_total_cents(rate_cents_per_hour: int, duration: str) -> int:
    """Compute a line-item total for a canonical duration."""
    if not is_canonical(duration):
        raise ValueError(f"non-canonical duration on invoice: {duration!r}")
    seconds = parse_duration(duration)
    return round(rate_cents_per_hour * seconds / 3600)
