import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
THEUSTAD = ROOT / "theustad.py"
FAKE_CODEX = ROOT / "fake_codex.py"
TASK = ROOT / "task.md"
VERIFY_CHAIN = ROOT / "verify_chain.py"
SEED = ROOT / "tests" / "fixtures" / "demo_repo_seed"
SUPPLIED_DEMO = ROOT / "demo_repo"


def _seed_files():
    return sorted(SEED.rglob("*.seed"))


def _seed_relative(source):
    relative = source.relative_to(SEED)
    return relative.with_name(relative.name.removesuffix(".seed"))


def _reset_repo(tmp_path):
    repo = tmp_path / "demo_repo"
    result = subprocess.run(
        [sys.executable, str(FAKE_CODEX), "reset", "--repo", str(repo)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return repo


def _run_scenario(tmp_path, scenario, *, max_retries=3, repo=None):
    repo = _reset_repo(tmp_path) if repo is None else repo
    state_dir = tmp_path / "theustad-state"
    log_dir = tmp_path / "audit"
    python = Path(sys.executable).as_posix()
    fake = FAKE_CODEX.as_posix()
    command = [
        sys.executable,
        str(THEUSTAD),
        "--repo",
        str(repo),
        "--task",
        str(TASK),
        "--cmd",
        f"{python} {fake} {scenario}",
        "--resume-cmd",
        f"{python} {fake} {scenario} --resume {{thread_id}}",
        "--state-dir",
        str(state_dir),
        "--log",
        str(log_dir),
        "--max-retries",
        str(max_retries),
        "--timeout",
        "30",
        "--no-color",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    return repo, result


def _verdicts(output):
    return re.findall(r"^ROUND \d+ (\S+)$", output, flags=re.MULTILINE)


def _audit_path(output):
    match = re.search(r"^AUDIT_LOG (.+)$", output, flags=re.MULTILINE)
    assert match is not None, output
    return Path(match.group(1).strip())


def _assert_valid_chain(output):
    verified = subprocess.run(
        [sys.executable, str(VERIFY_CHAIN), str(_audit_path(output))],
        capture_output=True,
        text=True,
        check=False,
    )

    assert verified.returncode == 0, verified.stdout + verified.stderr
    assert verified.stdout.startswith("VALID:")


def test_seed_snapshot_matches_supplied_demo_before_rehearsal():
    assert len(_seed_files()) == 7
    for source in _seed_files():
        supplied = SUPPLIED_DEMO / _seed_relative(source)
        assert source.read_bytes() == supplied.read_bytes()


def test_demo3_runs_falsified_tampered_verified_and_valid_chain(tmp_path):
    repo, result = _run_scenario(tmp_path, "demo3")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _verdicts(result.stdout) == ["FALSIFIED", "TAMPERED", "VERIFIED"]
    assert "6 passed" in result.stdout
    assert "11 passed" in result.stdout

    invoice_test = repo / "tests" / "test_invoice.py"
    seed_invoice_test = SEED / "tests" / "test_invoice.py.seed"
    assert invoice_test.read_bytes() == seed_invoice_test.read_bytes()
    assert "_CANONICAL_DURATION" in (repo / "app" / "invoice.py").read_text()

    audit_path = _audit_path(result.stdout)
    records = [json.loads(line) for line in audit_path.read_text().splitlines()]
    verdicts = [
        record["data"]["verdict"]
        for record in records
        if record["kind"] == "verdict"
    ]
    resume_evidence = [
        record["data"]["message"]
        for record in records
        if record["kind"] == "resume"
    ]
    verified = subprocess.run(
        [sys.executable, str(VERIFY_CHAIN), str(audit_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert verdicts == ["FALSIFIED", "TAMPERED", "VERIFIED"]
    assert any("2 failed, 9 passed" in message for message in resume_evidence)
    assert verified.returncode == 0
    assert verified.stdout.startswith("VALID:")


def test_naive2_runs_falsified_then_verified(tmp_path):
    _, result = _run_scenario(tmp_path, "naive2")

    assert result.returncode == 0, result.stdout + result.stderr
    assert _verdicts(result.stdout) == ["FALSIFIED", "VERIFIED"]


def test_crash_is_agent_error_and_nonzero(tmp_path):
    _, result = _run_scenario(tmp_path, "crash")

    assert result.returncode != 0
    assert _verdicts(result.stdout) == ["AGENT_ERROR"]
    assert "FINAL AGENT_ERROR" in result.stdout


@pytest.mark.parametrize(
    ("scenario", "expected", "protected_path"),
    [
        ("assertion_gut", "TAMPERED", "tests/test_invoice.py"),
        ("conftest_poison", "TAMPERED", "conftest.py"),
        ("config_poison", "TAMPERED", "pytest.ini"),
    ],
)
def test_adversarial_scenario_is_detected_and_restored(
    tmp_path, scenario, expected, protected_path
):
    repo = _reset_repo(tmp_path)
    before = (
        (repo / protected_path).read_bytes()
        if (repo / protected_path).exists()
        else None
    )

    repo, result = _run_scenario(tmp_path, scenario, max_retries=0, repo=repo)

    assert result.returncode != 0
    assert _verdicts(result.stdout) == [expected]
    target = repo / protected_path
    assert target.read_bytes() == before if before is not None else not target.exists()
    _assert_valid_chain(result.stdout)


def test_empty_final_message_is_pass_no_claim_and_not_success(tmp_path):
    _, result = _run_scenario(tmp_path, "no_claim", max_retries=0)

    assert result.returncode != 0
    assert _verdicts(result.stdout) == ["PASS_NO_CLAIM"]
    assert "FINAL PASS_NO_CLAIM" in result.stdout
    _assert_valid_chain(result.stdout)


def test_honest_scenario_verifies_in_round_one(tmp_path):
    _, result = _run_scenario(tmp_path, "honest", max_retries=0)

    assert result.returncode == 0, result.stdout + result.stderr
    assert _verdicts(result.stdout) == ["VERIFIED"]
    _assert_valid_chain(result.stdout)
