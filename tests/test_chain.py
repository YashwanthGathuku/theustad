import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


VERIFY_CHAIN = Path(__file__).parents[1] / "verify_chain.py"
FIXED_TIME = datetime(2026, 7, 18, 12, 34, 56, tzinfo=timezone.utc)


def _audit_chain(tmp_path):
    try:
        from theustadlib.chain import AuditChain
    except ModuleNotFoundError:
        pytest.fail("theustadlib.chain is not implemented", pytrace=False)
    return AuditChain(tmp_path, clock=lambda: FIXED_TIME)


def _verify(path):
    return subprocess.run(
        [sys.executable, str(VERIFY_CHAIN), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_five_record_chain_is_byte_compatible_with_oracle(tmp_path):
    chain = _audit_chain(tmp_path)
    kinds = ["session", "claim", "verdict", "resume", "final"]

    for sequence, kind in enumerate(kinds):
        chain.append(
            round_number=(sequence // 2) + 1,
            kind=kind,
            data={"sequence": sequence, "detail": f"record {sequence}"},
        )

    records = [json.loads(line) for line in chain.path.read_text().splitlines()]
    assert [record["seq"] for record in records] == list(range(5))
    assert [record["kind"] for record in records] == kinds
    assert set(records[0]) == {"seq", "ts", "round", "kind", "data", "prev", "hash"}
    assert records[0]["prev"] == "0" * 64
    assert chain.root == records[-1]["hash"]

    result = _verify(chain.path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"VALID: 5 records, root {chain.root}"


def test_flipped_middle_record_is_broken_with_nonzero_exit(tmp_path):
    chain = _audit_chain(tmp_path)
    for sequence in range(5):
        chain.append(
            round_number=sequence + 1,
            kind="verdict",
            data={"value": sequence},
        )

    records = [json.loads(line) for line in chain.path.read_text().splitlines()]
    records[2]["data"]["value"] = "flipped"
    chain.path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    result = _verify(chain.path)

    assert result.returncode != 0
    assert result.stdout.strip() == "BROKEN at seq 2: hash mismatch"


def test_second_run_creates_distinct_timestamped_log_without_erasing_first(
    tmp_path,
):
    first = _audit_chain(tmp_path)
    first.append(round_number=1, kind="session", data={"run": 1})
    first_bytes = first.path.read_bytes()

    second = _audit_chain(tmp_path)
    second.append(round_number=1, kind="session", data={"run": 2})

    assert first.path.name == "audit_20260718_123456.jsonl"
    assert second.path.name == "audit_20260718_123457.jsonl"
    assert first.path != second.path
    assert first.path.read_bytes() == first_bytes
    assert sorted(tmp_path.glob("audit_*.jsonl")) == [first.path, second.path]


def test_resume_validates_and_appends_to_one_continuous_chain(tmp_path):
    first = _audit_chain(tmp_path)
    first.append(round_number=0, kind="session", data={"event": "start"})

    from theustadlib.chain import AuditChain, verify

    resumed = AuditChain.resume(first.path, clock=lambda: FIXED_TIME)
    resumed.append(round_number=1, kind="verdict", data={"verdict": "VERIFIED"})

    assert resumed.path == first.path
    assert verify(first.path) == (2, resumed.root)
    records = [json.loads(line) for line in first.path.read_text().splitlines()]
    assert [record["seq"] for record in records] == [0, 1]
    assert records[1]["prev"] == records[0]["hash"]


def test_resume_refuses_a_rewritten_chain(tmp_path):
    chain = _audit_chain(tmp_path)
    chain.append(round_number=0, kind="session", data={"event": "start"})
    chain.path.write_text(chain.path.read_text().replace("start", "rewrite"))

    from theustadlib.chain import AuditChain

    with pytest.raises(ValueError, match="hash mismatch"):
        AuditChain.resume(chain.path)
