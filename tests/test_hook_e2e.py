import json
import os
import subprocess
import sys
from pathlib import Path


CLI = Path(__file__).parents[1] / "theustad.py"


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "app").mkdir()
    (repo / "tests" / "test_guard.py").write_text(
        "def test_guard():\n    assert True\n"
    )
    (repo / "app" / "code.py").write_text("VALUE = 1\n")
    (repo / "pytest.ini").write_text("[pytest]\n")
    return repo


def _run(args, *, env, payload=None):
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        input=json.dumps(payload) if payload is not None else None,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _start(repo: Path):
    return {
        "session_id": "e2e-session",
        "transcript_path": "/tmp/transcript.jsonl",
        "cwd": str(repo),
        "hook_event_name": "SessionStart",
        "source": "startup",
    }


def _stop(repo: Path, message="The fix is complete and all tests pass."):
    return {
        "session_id": "e2e-session",
        "transcript_path": "/tmp/transcript.jsonl",
        "cwd": str(repo),
        "permission_mode": "default",
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "last_assistant_message": message,
        "background_tasks": [],
        "session_crons": [],
    }


def test_cli_hook_lifecycle_verifies_an_honest_green_repo(tmp_path):
    repo = _repo(tmp_path)
    env = {**os.environ, "THEUSTAD_HOME": str(tmp_path / "external")}

    enroll = _run(["enroll", "--repo", str(repo)], env=env)
    start = _run(
        ["hook", "claude", "SessionStart"], env=env, payload=_start(repo)
    )
    stop = _run(["hook", "claude", "Stop"], env=env, payload=_stop(repo))

    assert enroll.returncode == 0, enroll.stderr
    assert start.returncode == 0, start.stderr
    assert stop.returncode == 0, stop.stderr
    assert "VERIFIED" in stop.stdout
    verify = _run(["verify-chain", "--repo", str(repo)], env=env)
    assert verify.returncode == 0, verify.stderr
    assert "VALID" in verify.stdout


def test_cli_hook_lifecycle_restores_deleted_test(tmp_path):
    repo = _repo(tmp_path)
    env = {**os.environ, "THEUSTAD_HOME": str(tmp_path / "external")}
    assert _run(["enroll", "--repo", str(repo)], env=env).returncode == 0
    assert _run(
        ["hook", "claude", "SessionStart"], env=env, payload=_start(repo)
    ).returncode == 0
    protected = repo / "tests" / "test_guard.py"
    protected.unlink()

    stop = _run(["hook", "claude", "Stop"], env=env, payload=_stop(repo))

    assert stop.returncode == 2
    assert "TAMPERED" in stop.stderr
    assert protected.read_text() == "def test_guard():\n    assert True\n"


def test_cli_hook_lifecycle_catches_project_hook_disable_config(tmp_path):
    repo = _repo(tmp_path)
    env = {**os.environ, "THEUSTAD_HOME": str(tmp_path / "external")}
    assert _run(["enroll", "--repo", str(repo)], env=env).returncode == 0
    assert _run(
        ["hook", "claude", "SessionStart"], env=env, payload=_start(repo)
    ).returncode == 0
    (repo / ".claude").mkdir()
    settings = repo / ".claude" / "settings.json"
    settings.write_text('{"disableAllHooks": true}\n')

    stop = _run(["hook", "claude", "Stop"], env=env, payload=_stop(repo))

    assert stop.returncode == 2
    assert "TAMPERED" in stop.stderr
    assert not settings.exists()
