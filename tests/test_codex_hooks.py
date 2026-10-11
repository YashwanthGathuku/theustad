"""Hook mode for the Codex CLI: its own payloads, its own output contract."""

import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from theustadlib import enrollment, hookadapter
from theustadlib.verifier import VerificationResult, default_argv


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "hooks" / "codex"
CLAUDE_FIXTURES = Path(__file__).parent / "fixtures" / "hooks" / "claude"
# Every key a Codex Stop hook may print on stdout; it rejects any other
# (codex-cli 0.162.1, stop.command.output.schema.json).
CODEX_STOP_OUTPUT_KEYS = {
    "continue",
    "decision",
    "reason",
    "stopReason",
    "suppressOutput",
    "systemMessage",
}
CODEX_SESSION_START_OUTPUT_KEYS = {
    "continue",
    "hookSpecificOutput",
    "stopReason",
    "suppressOutput",
    "systemMessage",
}


def _seed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_guard.py").write_text("def test_guard():\n    assert True\n")
    (repo / "pytest.ini").write_text("[pytest]\n")
    return repo


def _enroll(tmp_path, monkeypatch) -> Path:
    repo = _seed_repo(tmp_path)
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    enrollment.save_policy(
        enrollment.Policy(repo=str(repo), verifier_argv=tuple(default_argv()), census=False)
    )
    return repo


def _payload(name, repo, *, session_id="codex-session", **updates):
    value = json.loads((FIXTURES / name).read_text())
    value.update({"cwd": str(repo), "session_id": session_id, **updates})
    return value


def _result(exit_code):
    output = "1 passed\n" if exit_code == 0 else "1 failed\n"
    return VerificationResult(
        argv=(sys.executable, "-c", "pass"),
        exit_code=exit_code,
        output=output,
        tail=(output.strip(),),
        timed_out=False,
        warning=None,
    )


def _assert_codex_accepts(response, event):
    """What Codex does with this response: allow, or block with a reason."""
    if response.exit_code == hookadapter.ALLOW:
        allowed = CODEX_STOP_OUTPUT_KEYS if event == "Stop" else CODEX_SESSION_START_OUTPUT_KEYS
        assert set(response.stdout or {}) <= allowed
    else:
        # Exit 2 blocks in Codex only with a continuation prompt on stderr;
        # without one, the stop goes through.
        assert response.exit_code == hookadapter.BLOCK
        assert response.stderr.strip()


def test_recorded_codex_payloads_parse(tmp_path):
    repo = _seed_repo(tmp_path)

    start = hookadapter.parse_codex(_payload("session_start.json", repo))
    stop = hookadapter.parse_codex(_payload("stop_claim.json", repo))

    assert (start.event, start.source) == ("session_start", "startup")
    assert (stop.event, stop.stop_active) == ("stop", False)
    assert stop.last_assistant_message == "All done, the tests pass."
    assert stop.background_tasks == () and stop.session_crons == ()


def test_a_null_last_message_is_no_claim(tmp_path):
    repo = _seed_repo(tmp_path)

    event = hookadapter.parse_codex(
        _payload("stop_claim.json", repo, last_assistant_message=None)
    )

    assert event.last_assistant_message == ""


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("turn_id", None),
        ("model", None),
        ("permission_mode", None),
        ("stop_hook_active", "false"),
        ("last_assistant_message", 7),
        ("transcript_path", 7),
        ("session_id", ""),
    ],
)
def test_a_malformed_codex_stop_fails_closed(tmp_path, field, value):
    repo = _seed_repo(tmp_path)
    payload = _payload("stop_claim.json", repo)
    if value is None:
        del payload[field]
    else:
        payload[field] = value

    with pytest.raises(ValueError, match=field):
        hookadapter.parse_codex(payload)


@pytest.mark.parametrize("event_name", ["SubagentStop", "SessionEnd", "PreToolUse"])
def test_only_session_start_and_stop_are_codex_events(tmp_path, event_name):
    repo = _seed_repo(tmp_path)

    with pytest.raises(ValueError, match="unsupported Codex hook event"):
        hookadapter.parse_codex(_payload("stop_claim.json", repo, hook_event_name=event_name))


def test_a_claude_payload_is_not_a_codex_payload(tmp_path):
    # Similar-looking schemas are never treated as interchangeable.
    repo = _seed_repo(tmp_path)
    claude = json.loads((CLAUDE_FIXTURES / "stop_claim.json").read_text())
    claude["cwd"] = str(repo)

    with pytest.raises(ValueError, match="model|turn_id|permission_mode"):
        hookadapter.parse_codex(claude)


def test_a_codex_session_is_verified_blocked_and_restored(tmp_path, monkeypatch):
    repo = _enroll(tmp_path, monkeypatch)
    monkeypatch.setattr(hookadapter, "run_verifier", lambda *_args: _result(0))

    start = hookadapter.dispatch("codex", _payload("session_start.json", repo))
    _assert_codex_accepts(start, "SessionStart")
    assert start.exit_code == hookadapter.ALLOW

    verified = hookadapter.dispatch("codex", _payload("stop_claim.json", repo))
    _assert_codex_accepts(verified, "Stop")
    assert "VERIFIED" in verified.stdout["systemMessage"]

    (repo / "tests" / "test_guard.py").unlink()
    tampered = hookadapter.dispatch(
        "codex", _payload("stop_claim.json", repo, stop_hook_active=True)
    )
    _assert_codex_accepts(tampered, "Stop")
    assert tampered.exit_code == hookadapter.BLOCK
    assert "TAMPERED" in tampered.stderr
    assert (repo / "tests" / "test_guard.py").is_file()


def test_failing_tests_send_codex_back_with_the_evidence(tmp_path, monkeypatch):
    repo = _enroll(tmp_path, monkeypatch)
    monkeypatch.setattr(hookadapter, "run_verifier", lambda *_args: _result(1))
    hookadapter.dispatch("codex", _payload("session_start.json", repo))

    response = hookadapter.dispatch("codex", _payload("stop_claim.json", repo))

    _assert_codex_accepts(response, "Stop")
    assert response.exit_code == hookadapter.BLOCK
    assert "FALSIFIED" in response.stderr and "1 failed" in response.stderr


def test_a_stop_without_session_start_names_codex(tmp_path, monkeypatch):
    repo = _enroll(tmp_path, monkeypatch)

    response = hookadapter.dispatch("codex", _payload("stop_claim.json", repo))

    assert response.exit_code == hookadapter.BLOCK
    assert "restart Codex" in response.stderr


def test_codex_and_claude_sessions_with_one_id_stay_apart(tmp_path, monkeypatch):
    repo = _enroll(tmp_path, monkeypatch)
    claude = json.loads((CLAUDE_FIXTURES / "session_start.json").read_text())
    claude.update({"cwd": str(repo), "session_id": "shared-id"})

    hookadapter.dispatch("codex", _payload("session_start.json", repo, session_id="shared-id"))

    assert enrollment.load_binding("codex", "shared-id") is not None
    assert enrollment.load_binding("claude", "shared-id") is None


def test_a_block_never_reaches_codex_without_a_reason(monkeypatch, capsys):
    # Codex lets a stop through on exit 2 when stderr is empty.
    monkeypatch.setattr(
        hookadapter, "dispatch", lambda *_a, **_k: hookadapter.HookResponse(hookadapter.BLOCK)
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))

    assert hookadapter.main(["codex", "Stop"]) == hookadapter.BLOCK
    assert capsys.readouterr().err.strip()


def test_the_cli_routes_codex_hooks(tmp_path):
    repo = _seed_repo(tmp_path)
    environment = {**os.environ, "THEUSTAD_HOME": str(tmp_path / "external")}
    enrolled = subprocess.run(
        [sys.executable, str(ROOT / "theustad.py"), "enroll", "--repo", str(repo), "--no-census"],
        capture_output=True, text=True, env=environment, check=False,
    )
    assert enrolled.returncode == 0, enrolled.stderr

    def hook(event, payload):
        return subprocess.run(
            [sys.executable, str(ROOT / "theustad.py"), "hook", "codex", event],
            input=json.dumps(payload), capture_output=True, text=True,
            env=environment, cwd=repo, check=False,
        )

    assert hook("SessionStart", _payload("session_start.json", repo)).returncode == 0
    (repo / "tests" / "test_guard.py").unlink()
    blocked = hook("Stop", _payload("stop_claim.json", repo))

    assert blocked.returncode == 2
    assert "TAMPERED" in blocked.stderr
    assert (repo / "tests" / "test_guard.py").is_file()
