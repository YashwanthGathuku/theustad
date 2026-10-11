"""TheUstad's Codex hooks under the real Codex CLI.

These run `codex exec` against a local stand-in for the model API, so they
need the Codex binary but no account: set THEUSTAD_CODEX_BIN, or put `codex`
on PATH.  Recorded passing with codex-cli 0.162.1.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from theustadlib import claudesettings, codexsettings


ROOT = Path(__file__).resolve().parents[1]
MOCK = Path(__file__).parent / "fixtures" / "codex_mock_responses.py"
CODEX = os.environ.get("THEUSTAD_CODEX_BIN") or shutil.which("codex")

pytestmark = [
    pytest.mark.skipif(CODEX is None, reason="Codex CLI not installed"),
    pytest.mark.skipif(os.name != "posix", reason="hook mode is POSIX-only"),
]


@pytest.fixture
def world(tmp_path, monkeypatch):
    home = tmp_path / "codex"
    home.mkdir()
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_guard.py").write_text("def test_guard():\n    assert True\n")
    (repo / "pytest.ini").write_text("[pytest]\n")
    environment = {
        **os.environ,
        "CODEX_HOME": str(home),
        "CODEX_SQLITE_HOME": str(home),
        "CODEX_API_KEY": "dummy",
        "THEUSTAD_HOME": str(tmp_path / "external"),
    }
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    return tmp_path, home, repo, environment


def _theustad(environment, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / "theustad.py"), *args],
        capture_output=True, text=True, env=environment, check=False,
    )


def _trust_like_hooks_command(home):
    """Record trust exactly as approving both hooks in Codex's /hooks does."""
    path = home / "hooks.json"
    settings = json.loads(path.read_text())
    lines = [
        f'[hooks.state.{json.dumps(key)}]\ntrusted_hash = "{codexsettings.handler_hash(event, item, matcher)}"\n'
        for event, key, item, matcher in codexsettings._our_entries(path, settings)
    ]
    assert len(lines) == 2
    (home / "config.toml").write_text("\n".join(lines))


def _run_codex(tmp_path, repo, environment, script, *, timeout=180):
    (tmp_path / "script.txt").write_text("\n".join(script) + "\n")
    log = tmp_path / "requests.log"
    log.write_text("")
    port_file = tmp_path / "port"
    server = subprocess.Popen(
        [sys.executable, str(MOCK), str(port_file), str(tmp_path / "script.txt"), str(log)]
    )
    try:
        for _ in range(100):
            if port_file.exists() and port_file.read_text():
                break
            time.sleep(0.05)
        port = port_file.read_text()
        completed = subprocess.run(
            [CODEX, "exec", "--json", "--skip-git-repo-check",
             "-c", f'openai_base_url="http://127.0.0.1:{port}/v1"', "Fix the parser."],
            cwd=repo, env=environment, stdin=subprocess.DEVNULL,
            capture_output=True, text=True, timeout=timeout, check=False,
        )
    finally:
        server.terminate()
        server.wait()
    requests = [line for line in log.read_text().splitlines() if line]
    return completed, requests


def _verdicts(environment, repo):
    status = _theustad(environment, "status", "--repo", str(repo))
    state = Path(environment["THEUSTAD_HOME"])
    records = [
        json.loads(line)
        for audit in state.glob("state/*/*/logs/audit_*.jsonl")
        for line in audit.read_text().splitlines()
    ]
    return status.stdout, [r["data"]["verdict"] for r in records if r["kind"] == "verdict"]


def test_codex_is_sent_back_when_it_tampers_and_verified_when_it_does_not(world):
    tmp_path, home, repo, environment = world
    assert _theustad(environment, "install-hooks", "--agent", "codex").returncode == 0
    _trust_like_hooks_command(home)
    assert _theustad(environment, "enroll", "--repo", str(repo), "--no-census").returncode == 0

    guard = repo / "tests" / "test_guard.py"
    completed, requests = _run_codex(tmp_path, repo, environment, [
        f"TAMPER:{guard}|I fixed the parser and all tests pass.",
        "I restored the test; the fix is complete and all tests pass.",
    ])

    assert completed.returncode == 0, completed.stderr[-2000:]
    # TheUstad's TAMPERED verdict went back to the model as the next prompt.
    assert len(requests) == 2
    assert "TAMPERED" in json.loads(json.loads(requests[1])["body"])["input"][-1]["content"][0]["text"]
    assert guard.is_file()
    status, verdicts = _verdicts(environment, repo)
    assert verdicts == ["TAMPERED", "VERIFIED"]
    assert "CODEX_HOOKS installed" in status
    chain = _theustad(environment, "verify-chain", "--repo", str(repo), "--vendor", "codex")
    assert chain.returncode == 0 and "VALID" in chain.stdout


def test_hooks_codex_has_not_trusted_never_run(world):
    tmp_path, home, repo, environment = world
    _theustad(environment, "install-hooks", "--agent", "codex")
    _theustad(environment, "enroll", "--repo", str(repo), "--no-census")

    guard = repo / "tests" / "test_guard.py"
    completed, requests = _run_codex(
        tmp_path, repo, environment, [f"TAMPER:{guard}|All tests pass."]
    )

    assert completed.returncode == 0
    assert len(requests) == 1 and not guard.exists()
    status, verdicts = _verdicts(environment, repo)
    assert verdicts == []
    # Python 3.10 cannot read config.toml, so it can only say trust is unknown.
    assert "CODEX_HOOKS untrusted" in status or "trust unknown" in status


def test_a_deleted_clone_does_not_trap_codex_in_a_loop(world):
    # Python exits 2 with an error on stderr for a missing script, which Codex
    # reads as a block; it sets no limit on those, so the guard lets it stop.
    tmp_path, home, repo, environment = world
    missing = tmp_path / "gone" / "theustad.py"
    settings = claudesettings.with_hooks({}, sys.executable, str(missing), vendor="codex")
    claudesettings.write_settings(home / "hooks.json", settings)
    _trust_like_hooks_command(home)
    _theustad(environment, "enroll", "--repo", str(repo), "--no-census")

    completed, requests = _run_codex(
        tmp_path, repo, environment, ["All tests pass."], timeout=60
    )

    assert completed.returncode == 0
    assert len(requests) == 1
    status, _ = _verdicts(environment, repo)
    assert "CODEX_HOOKS stale" in status
