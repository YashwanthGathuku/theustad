#!/usr/bin/env python3
"""Independently verify a TheUstad audit chain. Recomputes every hash.

This oracle deliberately shares no code with ``theustadlib.chain`` so that a
record TheUstad accepts is checked twice, by two independent implementations.
It must therefore apply exactly the same rules: sequence numbers, prev-links,
hashes, and UTF-8 bytes.
"""
import hashlib
import json
import sys


def _broken(seq, reason):
    print(f"BROKEN at seq {seq}: {reason}")
    sys.exit(1)


def main(path):
    prev = "0" * 64
    n = 0
    try:
        handle = open(path, "r", encoding="utf-8")
    except OSError as error:
        print(f"ERROR cannot read audit chain: {error}", file=sys.stderr)
        sys.exit(2)

    with handle:
        for i, line in enumerate(handle):
            try:
                rec = json.loads(line)
            except (UnicodeDecodeError, ValueError):
                _broken(i, "invalid JSON")
            if not isinstance(rec, dict):
                _broken(i, "record is not an object")
            if "hash" not in rec:
                _broken(i, "record has no hash")
            claimed = rec.pop("hash")
            if rec.get("seq") != i:
                _broken(i, "sequence mismatch")
            if rec.get("prev") != prev:
                _broken(i, "prev-link mismatch")
            payload = json.dumps(rec, sort_keys=True, separators=(",", ":"))
            actual = hashlib.sha256((prev + payload).encode("utf-8")).hexdigest()
            if actual != claimed:
                _broken(i, "hash mismatch")
            prev = claimed
            n += 1

    if n == 0:
        # A truncated or emptied log must never read as a successful audit.
        print("BROKEN at seq 0: audit chain is empty")
        sys.exit(1)
    print(f"VALID: {n} records, root {prev}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "audit_log.jsonl")
