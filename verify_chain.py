#!/usr/bin/env python3
"""Independently verify a gate audit chain. Recomputes every hash."""
import hashlib, json, sys

def main(path):
    prev = "0" * 64
    n = 0
    for i, line in enumerate(open(path)):
        rec = json.loads(line)
        claimed = rec.pop("hash")
        if rec["prev"] != prev:
            print(f"BROKEN at seq {i}: prev-link mismatch"); sys.exit(1)
        payload = json.dumps(rec, sort_keys=True, separators=(",", ":"))
        actual = hashlib.sha256((prev + payload).encode()).hexdigest()
        if actual != claimed:
            print(f"BROKEN at seq {i}: hash mismatch"); sys.exit(1)
        prev = claimed
        n += 1
    print(f"VALID: {n} records, root {prev}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "audit_log.jsonl")
