import io
import json
import sys
from pathlib import Path

import pytest

from theustadlib import enrollment, hookadapter
from theustadlib.verifier import VerificationResult, default_argv


FIXTURES = Path(__file__).parent / "fixtures" / "hooks" / "claude"


def _seed_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "app").mkdir()
    (repo / "tests" / "test_guard.py").write_text(
        "def test_guard():\n    assert True\n"
    )
    (repo / "app" / "code.py").write_text("VALUE = 1\n")
    (repo / "pytest.ini").write_text("[pytest]\n")
    return repo


def _result(exit_code: int, *, timed_out: bool = False) -> VerificationResult:
    output = "1 passed\n" if exit_code == 0 else "1 failed\n"
    return VerificationResult(
        argv=(sys.executable, "-c", "pass"),
        exit_code=exit_code,
        output=output,
        tail=(output.strip(),),
        timed_out=timed_out,
        warning=None,
    )


def _enroll(
    tmp_path: Path,
    monkeypatch,
    *,
    max_blocks: int = 5,
    require_claim: bool = False,
) -> Path:
    repo = _seed_repo(tmp_path)
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))
    enrollment.save_policy(
        enrollment.Policy(
            repo=str(repo),
            verifier_argv=tuple(default_argv()),
            max_blocks=max_blocks,
            require_claim=require_claim,
        )
    )
    return repo


def _payload(name: str, repo: Path, *, session_id: str = "session-1", **updates):
    value = json.loads((FIXTURES / name).read_text())
    value.update({"cwd": str(repo), "session_id": session_id})
    value.update(updates)
    return value


def _start(repo: Path, *, session_id: str = "session-1"):
    return hookadapter.dispatch(
        "claude", _payload("session_start.json", repo, session_id=session_id)
    )


def _stop(repo: Path, *, session_id: str = "session-1", **updates):
    return hookadapter.dispatch(
        "claude",
        _payload("stop_claim.json", repo, session_id=session_id, **updates),
    )


def _audit_records(repo: Path, session_id: str = "session-1"):
    binding = enrollment.load_binding("claude", session_id)
    return [
        json.loads(line)
        for line in Path(binding.audit_path).read_text().splitlines()
    ]


def test_official_fixture_fields_parse_without_transcript_scraping(tmp_path):
    repo = _seed_repo(tmp_path)
    event = hookadapter.parse_claude(_payload("stop_claim.json", repo))

    assert event.event == "stop"
    assert event.session_id == "session-1"
    assert event.last_assistant_message == (
        "The fix is complete and all tests pass."
    )


@pytest.mark.parametrize("event_name", ["SubagentStop", "StopFailure", "AfterAgent"])
def test_event_parser_uses_exact_names(event_name, tmp_path):
    repo = _seed_repo(tmp_path)
    payload = _payload("stop_claim.json", repo, hook_event_name=event_name)

    with pytest.raises(ValueError, match="unsupported"):
        hookadapter.parse_claude(payload)


def test_missing_identity_fields_fail_closed(tmp_path):
    repo = _seed_repo(tmp_path)
    payload = _payload("stop_claim.json", repo)
    del payload["session_id"]

    with pytest.raises(ValueError, match="session_id"):
        hookadapter.parse_claude(payload)


def test_stop_requires_last_assistant_message_field(tmp_path):
    repo = _seed_repo(tmp_path)
    payload = _payload("stop_claim.json", repo)
    del payload["last_assistant_message"]

    with pytest.raises(ValueError, match="last_assistant_message"):
        hookadapter.parse_claude(payload)


def test_real_claim_green_verifier_is_visible_verified(tmp_path, monkeypatch):
    repo = _enroll(tmp_path, monkeypatch)
    monkeypatch.setattr(hookadapter, "run_verifier", lambda *_args: _result(0))

    assert _start(repo).exit_code == hookadapter.ALLOW
    response = _stop(repo)

    assert response.exit_code == hookadapter.ALLOW
    assert "VERIFIED" in response.stdout["systemMessage"]
    records = _audit_records(repo)
    assert records[-1]["data"]["verdict"] == "VERIFIED"
    assert records[-1]["seq"] == 2


def test_deleted_test_is_tampered_and_restored(tmp_path, monkeypatch):
    repo = _enroll(tmp_path, monkeypatch)
    _start(repo)
    protected = repo / "tests" / "test_guard.py"
    protected.unlink()

    response = _stop(repo)

    assert response.exit_code == hookadapter.BLOCK
    assert "TAMPERED" in response.stderr
    assert protected.read_text() == "def test_guard():\n    assert True\n"


@pytest.mark.parametrize("source", ["compact", "resume"])
def test_reentered_sessionstart_cannot_refreeze_tampering(
    tmp_path, monkeypatch, source
):
    repo = _enroll(tmp_path, monkeypatch)
    _start(repo)
    protected = repo / "tests" / "test_guard.py"
    protected.write_text("def test_guard():\n    assert True  # weakened\n")
    compact = _payload(
        "session_start.json", repo, source=source, session_id="session-1"
    )

    assert hookadapter.dispatch("claude", compact).exit_code == hookadapter.ALLOW
    response = _stop(repo)

    assert response.exit_code == hookadapter.BLOCK
    assert "TAMPERED" in response.stderr
    assert protected.read_text() == "def test_guard():\n    assert True\n"
    session_records = [
        record for record in _audit_records(repo) if record["kind"] == "session"
    ]
    assert session_records[-1]["data"]["baseline_preserved"] is True


def test_repeated_sessionstart_cannot_move_bound_session_to_another_repo(
    tmp_path, monkeypatch
):
    repo = _enroll(tmp_path, monkeypatch)
    _start(repo)
    outside = tmp_path / "outside"
    outside.mkdir()
    compact = _payload(
        "session_start.json", outside, source="compact", session_id="session-1"
    )

    with pytest.raises(ValueError, match="bound repository"):
        hookadapter.dispatch("claude", compact)


def test_failed_initial_sessionstart_cannot_rebaseline_changed_inputs(
    tmp_path, monkeypatch
):
    repo = _enroll(tmp_path, monkeypatch)
    real_save_binding = enrollment.save_binding

    def fail_binding(_binding):
        raise OSError("simulated binding write failure")

    monkeypatch.setattr(enrollment, "save_binding", fail_binding)
    with pytest.raises(OSError, match="binding write failure"):
        _start(repo)

    protected = repo / "tests" / "test_guard.py"
    protected.write_text("def test_guard():\n    assert True  # weakened\n")
    monkeypatch.setattr(enrollment, "save_binding", real_save_binding)

    with pytest.raises(ValueError, match="unbound session state"):
        _start(repo)


def test_stop_uses_session_bound_repo_when_cwd_is_subdirectory(
    tmp_path, monkeypatch
):
    repo = _enroll(tmp_path, monkeypatch)
    observed = {}

    def verifier(_argv, cwd, _timeout):
        observed["cwd"] = cwd
        return _result(0)

    monkeypatch.setattr(hookadapter, "run_verifier", verifier)
    _start(repo)
    response = _stop(repo / "app")

    assert response.exit_code == hookadapter.ALLOW
    assert observed["cwd"] == repo.resolve()


def test_enrolled_stop_without_baseline_blocks(tmp_path, monkeypatch):
    repo = _enroll(tmp_path, monkeypatch)

    response = _stop(repo)

    assert response.exit_code == hookadapter.BLOCK
    assert "no protected-input baseline" in response.stderr


def test_unenrolled_repository_is_ignored(tmp_path, monkeypatch):
    repo = _seed_repo(tmp_path)
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "external"))

    assert _start(repo).exit_code == hookadapter.ALLOW
    assert _stop(repo).exit_code == hookadapter.ALLOW


def test_no_claim_green_is_pass_no_claim_not_verified(tmp_path, monkeypatch):
    repo = _enroll(tmp_path, monkeypatch)
    monkeypatch.setattr(hookadapter, "run_verifier", lambda *_args: _result(0))
    _start(repo)

    response = _stop(repo, last_assistant_message="I inspected the parser.")

    assert response.exit_code == hookadapter.ALLOW
    assert "PASS_NO_CLAIM" in response.stdout["systemMessage"]
    assert "not VERIFIED" in response.stdout["systemMessage"]


def test_require_claim_blocks_a_green_neutral_response(tmp_path, monkeypatch):
    repo = _enroll(tmp_path, monkeypatch, require_claim=True)
    monkeypatch.setattr(hookadapter, "run_verifier", lambda *_args: _result(0))
    _start(repo)

    response = _stop(repo, last_assistant_message="I inspected the parser.")

    assert response.exit_code == hookadapter.BLOCK
    assert "PASS_NO_CLAIM" in response.stderr


def test_red_claim_is_falsified_with_evidence(tmp_path, monkeypatch):
    repo = _enroll(tmp_path, monkeypatch)
    monkeypatch.setattr(hookadapter, "run_verifier", lambda *_args: _result(1))
    _start(repo)

    response = _stop(repo)

    assert response.exit_code == hookadapter.BLOCK
    assert "FALSIFIED" in response.stderr
    assert "1 failed" in response.stderr


def test_background_work_blocks_before_verifier_to_avoid_a_race(
    tmp_path, monkeypatch
):
    repo = _enroll(tmp_path, monkeypatch)
    _start(repo)
    called = False

    def verifier(*_args):
        nonlocal called
        called = True
        return _result(0)

    monkeypatch.setattr(hookadapter, "run_verifier", verifier)
    response = _stop(
        repo,
        background_tasks=[
            {"id": "task-1", "type": "shell", "status": "running"}
        ],
    )

    assert response.exit_code == hookadapter.BLOCK
    assert "BACKGROUND_ACTIVE" in response.stderr
    assert called is False


def test_scheduled_session_work_defers_verification(tmp_path, monkeypatch):
    repo = _enroll(tmp_path, monkeypatch)
    _start(repo)
    called = False

    def verifier(*_args):
        nonlocal called
        called = True
        return _result(0)

    monkeypatch.setattr(hookadapter, "run_verifier", verifier)
    response = _stop(
        repo,
        session_crons=[
            {"id": "cron-1", "schedule": "*/5 * * * *", "status": "scheduled"}
        ],
    )

    assert response.exit_code == hookadapter.BLOCK
    assert "BACKGROUND_ACTIVE" in response.stderr
    assert called is False


def test_verifier_tampering_is_caught_by_post_check(tmp_path, monkeypatch):
    repo = _enroll(tmp_path, monkeypatch)
    _start(repo)
    protected = repo / "tests" / "test_guard.py"

    def malicious_verifier(*_args):
        protected.write_text("def test_guard():\n    assert True  # changed\n")
        return _result(0)

    monkeypatch.setattr(hookadapter, "run_verifier", malicious_verifier)
    response = _stop(repo)

    assert response.exit_code == hookadapter.BLOCK
    assert "during verification" in response.stderr
    assert protected.read_text() == "def test_guard():\n    assert True\n"


def test_reenrollment_cannot_change_policy_mid_session(tmp_path, monkeypatch):
    repo = _enroll(tmp_path, monkeypatch)
    _start(repo)
    enrollment.save_policy(
        enrollment.Policy(repo=str(repo), verifier_argv=(sys.executable, "-c", "pass"))
    )
    observed = {}

    def verifier(argv, *_args):
        observed["argv"] = tuple(argv)
        return _result(1)

    monkeypatch.setattr(hookadapter, "run_verifier", verifier)
    response = _stop(repo)

    assert response.exit_code == hookadapter.BLOCK
    assert observed["argv"] == tuple(default_argv())


def test_stop_refuses_a_rewritten_session_audit(tmp_path, monkeypatch):
    repo = _enroll(tmp_path, monkeypatch)
    _start(repo)
    binding = enrollment.load_binding("claude", "session-1")
    audit_path = Path(binding.audit_path)
    audit_path.write_text(
        audit_path.read_text().replace("session_start", "rewritten_start"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="hash mismatch"):
        _stop(repo)


def test_retry_exhaustion_allows_stop_but_is_visibly_red(tmp_path, monkeypatch):
    repo = _enroll(tmp_path, monkeypatch, max_blocks=1)
    monkeypatch.setattr(hookadapter, "run_verifier", lambda *_args: _result(1))
    _start(repo)
    assert _stop(repo).exit_code == hookadapter.BLOCK

    response = _stop(repo, stop_hook_active=True)

    assert response.exit_code == hookadapter.ALLOW
    assert "FINAL RETRY_EXHAUSTED" in response.stdout["systemMessage"]
    records = _audit_records(repo)
    assert records[-1]["kind"] == "final"
    assert records[-1]["data"]["verified"] is False


@pytest.mark.parametrize("option", sorted(hookadapter.FORBIDDEN_POLICY_OPTIONS))
def test_policy_argument_injection_is_refused_before_stdin_or_state(
    tmp_path, monkeypatch, capsys, option
):
    state_home = tmp_path / "external"
    monkeypatch.setenv("THEUSTAD_HOME", str(state_home))
    monkeypatch.setattr(sys, "stdin", io.StringIO("not even JSON"))

    code = hookadapter.main(["claude", "Stop", f"{option}=attacker-controlled"])

    assert code == hookadapter.BLOCK
    assert "forbidden" in capsys.readouterr().err
    assert not state_home.exists()


def test_event_argument_must_match_payload(tmp_path, monkeypatch):
    repo = _enroll(tmp_path, monkeypatch)
    payload = _payload("session_start.json", repo)

    with pytest.raises(ValueError, match="does not match"):
        hookadapter.dispatch("claude", payload, expected_event="Stop")
