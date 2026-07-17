"""Duration string parsing.

Accepts strings like "2h", "45m", "1h30m" and returns total seconds.
"""

import re

_TOKEN = re.compile(r"(\d+)([hm])")

UNIT_SECONDS = {"h": 3600, "m": 60}


def parse_duration(s: str) -> int:
    """Parse a duration string like '1h30m' into seconds.

    Raises ValueError on empty input, unknown characters, or
    malformed token sequences.
    """
    if not isinstance(s, str) or not s.strip():
        raise ValueError("duration string is empty")

    s = s.strip().lower()

    matched = "".join(f"{n}{u}" for n, u in _TOKEN.findall(s))
    if matched != s:
        raise ValueError(f"malformed duration string: {s!r}")

    total = 0
    seen_units = set()
    for number, unit in _TOKEN.findall(s):
        if unit in seen_units:
            raise ValueError(f"duplicate unit {unit!r} in {s!r}")
        seen_units.add(unit)
        value = int(number)
        if unit == "m" and value >= 60:
            raise ValueError(
                f"minutes component must be < 60 in {s!r}; use hours"
            )
        total += value * UNIT_SECONDS[unit]

    return total
