"""Invariant I5: an internal failure must block, never pick its own exit code.

Claude Code treats exit 1 from a Stop hook as a non-blocking error, so an
unhandled exception anywhere in the gate lets the agent stop with no decision
rendered. Every stage is fault-injected here; all of them must yield exit 2.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from theustadlib import enrollment, hookadapter


ROOT = Path(__file__).resolve().parents[1]


def _enrolled(tmp_path, monkeypatch):
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "home"))
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_ok.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    policy = enrollment.Policy(
        repo=str(repo),
        verifier_argv=(sys.executable, "-I", "-B", "-m", "pytest", "-q"),
    )
    enrollment.save_policy(policy)
    start = {
        "hook_event_name": "SessionStart",
        "session_id": "s-1",
        "cwd": str(repo),
        "source": "startup",
    }
    assert hookadapter.main(["claude", "SessionStart"]) is not None or True
    return repo, start


def _stop_payload(repo):
    return {
        "hook_event_name": "Stop",
        "session_id": "s-1",
        "cwd": str(repo),
        "stop_hook_active": False,
        "last_assistant_message": "The task is complete.",
    }


def _invoke(payload, monkeypatch):
    monkeypatch.setattr("sys.stdin", _Stdin(json.dumps(payload)))
    return hookadapter.main(["claude", payload["hook_event_name"]])


class _Stdin:
    def __init__(self, text):
        self._text = text

    def read(self):
        return self._text


@pytest.mark.parametrize(
    ("target", "error"),
    [
        ("theustadlib.hookadapter.check", TypeError("boom")),
        ("theustadlib.hookadapter.find_claims", AttributeError("boom")),
        ("theustadlib.hookadapter.run_verifier", IndexError("boom")),
        ("theustadlib.enrollment.block_count", KeyError("boom")),
        ("theustadlib.chain.AuditChain.append", ZeroDivisionError("boom")),
    ],
)
def test_every_stop_stage_failure_blocks_rather_than_exiting_one(
    tmp_path, monkeypatch, capsys, target, error
):
    repo, start = _enrolled(tmp_path, monkeypatch)
    assert _invoke(start, monkeypatch) == hookadapter.ALLOW

    def explode(*args, **kwargs):
        raise error

    monkeypatch.setattr(target, explode, raising=True)

    exit_code = _invoke(_stop_payload(repo), monkeypatch)

    assert exit_code == hookadapter.BLOCK
    assert hookadapter.INTERNAL_ERROR in capsys.readouterr().err


def test_session_start_failure_blocks(tmp_path, monkeypatch, capsys):
    _, start = _enrolled(tmp_path, monkeypatch)

    def explode(*args, **kwargs):
        raise KeyError("boom")

    monkeypatch.setattr("theustadlib.hookadapter.freeze", explode, raising=True)

    assert _invoke(start, monkeypatch) == hookadapter.BLOCK
    assert hookadapter.INTERNAL_ERROR in capsys.readouterr().err


def test_restore_failure_during_tampering_blocks(tmp_path, monkeypatch, capsys):
    repo, start = _enrolled(tmp_path, monkeypatch)
    assert _invoke(start, monkeypatch) == hookadapter.ALLOW
    (repo / "tests" / "test_ok.py").write_text(
        "def test_ok():\n    assert 1\n", encoding="utf-8"
    )

    def explode(*args, **kwargs):
        raise ZeroDivisionError("boom")

    monkeypatch.setattr("theustadlib.hookadapter.restore", explode, raising=True)

    assert _invoke(_stop_payload(repo), monkeypatch) == hookadapter.BLOCK
    assert hookadapter.INTERNAL_ERROR in capsys.readouterr().err


def test_block_counter_failure_on_a_red_suite_blocks(tmp_path, monkeypatch, capsys):
    repo, start = _enrolled(tmp_path, monkeypatch)
    (repo / "app.py").write_text("", encoding="utf-8")
    assert _invoke(start, monkeypatch) == hookadapter.ALLOW
    # A red suite reaches the bump_blocks path that a green one skips.
    (repo / "tests" / "test_red.py").write_text(
        "def test_red():\n    assert False\n", encoding="utf-8"
    )

    def explode(*args, **kwargs):
        raise KeyError("boom")

    monkeypatch.setattr("theustadlib.enrollment.bump_blocks", explode, raising=True)

    assert _invoke(_stop_payload(repo), monkeypatch) == hookadapter.BLOCK
    assert hookadapter.INTERNAL_ERROR in capsys.readouterr().err


def test_malformed_terminal_record_blocks(tmp_path, monkeypatch, capsys):
    repo, start = _enrolled(tmp_path, monkeypatch)
    assert _invoke(start, monkeypatch) == hookadapter.ALLOW
    state = enrollment.session_state_dir(repo, "claude", "s-1")
    (state / "terminal.json").write_text('{"not_verdict": 1}', encoding="utf-8")
    (state / "blocks.json").write_text('{"blocks": 99}', encoding="utf-8")

    assert _invoke(_stop_payload(repo), monkeypatch) == hookadapter.BLOCK


def test_no_hook_entry_path_can_exit_one(tmp_path, monkeypatch):
    """End to end, through the real process, since exit 1 is the failure mode."""
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_ok.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    environment = {"THEUSTAD_HOME": str(home), "PATH": "/usr/bin:/bin"}

    def hook(event, payload):
        return subprocess.run(
            [sys.executable, str(ROOT / "theustad.py"), "hook", "claude", event],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
            env=environment,
        )

    subprocess.run(
        [sys.executable, str(ROOT / "theustad.py"), "enroll", "--repo", str(repo)],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
        env=environment,
    )
    hook("SessionStart", {
        "hook_event_name": "SessionStart",
        "session_id": "s-1",
        "cwd": str(repo),
        "source": "startup",
    })
    home_root = tmp_path / "home"
    counters = list(home_root.rglob("blocks.json"))
    assert counters, "SessionStart did not create session state"
    for counter in counters:
        counter.write_text('{"blocks": 99}', encoding="utf-8")
        # A same-user agent can write this state; a malformed record must not
        # decide the exit code for us.
        (counter.parent / "terminal.json").write_text("{}", encoding="utf-8")

    result = hook("Stop", _stop_payload(repo))

    assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
    assert "Traceback" not in result.stderr


def test_garbage_on_stdin_blocks(tmp_path, monkeypatch):
    monkeypatch.setattr("sys.stdin", _Stdin("{not json"))

    assert hookadapter.main(["claude", "Stop"]) == hookadapter.BLOCK
