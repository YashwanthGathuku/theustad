"""Wrapper mode on a frozen baseline: VERIFIED only when the claim is true."""

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
        shell=False,
    )
    return result.stdout.strip()


def _init_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "baseline"
    repo.mkdir()
    env = {
        "GIT_AUTHOR_NAME": "Yashwanth Gathuku",
        "GIT_AUTHOR_EMAIL": "90673620+YashwanthGathuku@users.noreply.github.com",
        "GIT_COMMITTER_NAME": "Yashwanth Gathuku",
        "GIT_COMMITTER_EMAIL": "90673620+YashwanthGathuku@users.noreply.github.com",
    }
    subprocess.run(["git", "init"], cwd=repo, check=True, env={**env}, capture_output=True)
    (repo / "MARKER").write_text("frozen\n", encoding="utf-8")
    subprocess.run(["git", "add", "MARKER"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "freeze baseline"],
        cwd=repo,
        check=True,
        capture_output=True,
        env=env,
    )
    return repo, _git(repo, "rev-parse", "HEAD")


def _run(tmp_path: Path, repo: Path, claim: str, verifier_ok: bool) -> subprocess.CompletedProcess[str]:
    outside = tmp_path / "outside"
    outside.mkdir(parents=True, exist_ok=True)
    claim_script = outside / "claim.py"
    claim_script.write_text(
        "import json\n"
        f"print(json.dumps({{'type': 'agent_message', 'text': {claim!r}}}))\n",
        encoding="utf-8",
    )
    verifier = outside / "verifier.py"
    verifier.write_text(
        "import pathlib, sys\n"
        "marker = pathlib.Path('MARKER').read_text(encoding='utf-8')\n"
        f"sys.exit(0 if marker == 'frozen\\n' and {verifier_ok!r} else 1)\n",
        encoding="utf-8",
    )
    python = Path(sys.executable).as_posix()
    command = [
        sys.executable,
        str(ROOT / "theustad.py"),
        "--repo",
        str(repo),
        "--cmd",
        f"{python} {claim_script.as_posix()}",
        "--verifier",
        f"{python} {verifier.as_posix()}",
        "--state-dir",
        str(outside / "state"),
        "--log",
        str(outside / "logs"),
        "--max-retries",
        "0",
        "--timeout",
        "30",
        "--no-color",
    ]
    return subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        shell=False,
    )


def test_frozen_baseline_is_verified_only_when_the_claim_is_true(tmp_path):
    repo, head = _init_repo(tmp_path)

    verified = _run(
        tmp_path / "pass",
        repo,
        "Baseline check complete.",
        True,
    )
    assert verified.returncode == 0, verified.stdout + verified.stderr
    assert "FINAL VERIFIED" in verified.stdout
    assert _git(repo, "rev-parse", "HEAD") == head
    assert _git(repo, "status", "--porcelain") == ""

    falsified = _run(
        tmp_path / "fail",
        repo,
        "Baseline check complete.",
        False,
    )
    assert falsified.returncode != 0, falsified.stdout + falsified.stderr
    assert "FINAL VERIFIED" not in falsified.stdout
    assert "FINAL FALSIFIED" in falsified.stdout

    no_claim = _run(
        tmp_path / "noclaim",
        repo,
        "Still looking at the baseline.",
        True,
    )
    assert no_claim.returncode != 0, no_claim.stdout + no_claim.stderr
    assert "FINAL VERIFIED" not in no_claim.stdout
    assert "FINAL PASS_NO_CLAIM" in no_claim.stdout
    assert _git(repo, "rev-parse", "HEAD") == head
