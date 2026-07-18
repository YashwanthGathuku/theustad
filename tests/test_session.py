import json
import os
import sys
import time
from pathlib import Path

import pytest


def _session_module():
    try:
        from gatelib import session
    except ImportError:
        pytest.fail("gatelib.session is not implemented", pytrace=False)
    return session


def _write_stub(tmp_path, source):
    stub = tmp_path / "agent_stub.py"
    stub.write_text(source, encoding="utf-8")
    return stub


def _new_session(tmp_path, stub, *, timeout=2):
    session = _session_module()
    return session.AgentSession(
        [sys.executable, str(stub), "start"],
        [sys.executable, str(stub), "resume", "{thread_id}"],
        tmp_path,
        timeout,
    )


def test_default_commands_match_verified_codex_cli_forms():
    session = _session_module()

    assert session.DEFAULT_INITIAL_CMD == (
        "codex",
        "exec",
        "--json",
        "--sandbox",
        "workspace-write",
    )
    assert session.DEFAULT_RESUME_TEMPLATE == (
        "codex",
        "exec",
        "resume",
        "--json",
        "{thread_id}",
    )


def test_start_streams_jsonl_and_retains_final_message_and_non_json_tail(
    tmp_path,
):
    stub = _write_stub(
        tmp_path,
        """
import json
import sys

print("stdout evidence", flush=True)
print(json.dumps({"type": "thread.started", "thread_id": "thread-first"}), flush=True)
print(json.dumps({"session_id": "thread-later"}), flush=True)
print(json.dumps({"type": "agent_message", "text": "intermediate"}), flush=True)
print("stderr evidence", file=sys.stderr, flush=True)
print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "final answer"}}), flush=True)
""",
    )
    agent = _new_session(tmp_path, stub)
    streamed = []

    result = agent.start("task body", on_line=streamed.append)

    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.argv[-1] == "task body"
    assert result.thread_id == "thread-first"
    assert agent.thread_id == "thread-first"
    assert result.last_agent_message == "final answer"
    assert agent.last_agent_message == "final answer"
    assert result.non_json_tail == ("stdout evidence", "stderr evidence")
    assert streamed[0] == "stdout evidence"
    assert "final answer" in streamed[-1]


def test_resume_uses_exact_captured_thread_id(tmp_path):
    stub = _write_stub(
        tmp_path,
        """
import json
import sys

if sys.argv[1] == "start":
    print(json.dumps({"thread_id": "thread-exact"}), flush=True)
    print(json.dumps({"type": "agent_message", "text": "started"}), flush=True)
else:
    print(json.dumps({"type": "agent_message", "text": json.dumps(sys.argv[1:])}), flush=True)
""",
    )
    agent = _new_session(tmp_path, stub)
    agent.start("initial task")

    result = agent.resume("fix the remaining failure")

    assert result.exit_code == 0
    assert result.argv[-2:] == ("thread-exact", "fix the remaining failure")
    assert json.loads(result.last_agent_message) == [
        "resume",
        "thread-exact",
        "fix the remaining failure",
    ]
    assert result.warnings == ()


def test_missing_thread_id_falls_back_to_last_with_warning(tmp_path):
    stub = _write_stub(
        tmp_path,
        """
import json
import sys
print(json.dumps({"type": "agent_message", "text": json.dumps(sys.argv[1:])}), flush=True)
""",
    )
    agent = _new_session(tmp_path, stub)

    result = agent.resume("report explicit status")

    assert result.argv[-2:] == ("--last", "report explicit status")
    assert json.loads(result.last_agent_message) == [
        "resume",
        "--last",
        "report explicit status",
    ]
    assert result.warnings == (
        "Missing thread id; resumed with --last instead of an exact session.",
    )


def test_nonzero_agent_exit_is_exposed(tmp_path):
    stub = _write_stub(
        tmp_path,
        """
import sys
print("agent failed", file=sys.stderr, flush=True)
raise SystemExit(2)
""",
    )
    agent = _new_session(tmp_path, stub)

    result = agent.start("task")

    assert result.exit_code == 2
    assert result.timed_out is False
    assert result.non_json_tail == ("agent failed",)


def test_silent_agent_timeout_is_enforced(tmp_path):
    stub = _write_stub(
        tmp_path,
        """
import time
time.sleep(30)
""",
    )
    agent = _new_session(tmp_path, stub, timeout=0.2)
    started = time.monotonic()

    result = agent.start("task")

    assert time.monotonic() - started < 3
    assert result.exit_code == 124
    assert result.timed_out is True
    assert result.non_json_tail[-1] == "AGENT_TIMEOUT after 0.2 seconds"
    assert result.warnings == ("AGENT_TIMEOUT after 0.2 seconds",)


def _pid_is_running(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False

    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.exists() and proc_stat.read_text().split()[2] == "Z":
        return False
    return True


def _assert_pid_stopped(pid):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if not _pid_is_running(pid):
            return
        time.sleep(0.05)
    pytest.fail(f"background child {pid} is still running")


@pytest.mark.skipif(os.name != "posix", reason="POSIX/WSL process groups required")
@pytest.mark.parametrize(("parent_delay", "timed_out"), [(0, False), (30, True)])
def test_process_group_terminates_background_child(
    tmp_path,
    parent_delay,
    timed_out,
):
    pid_file = tmp_path / "child.pid"
    stub = _write_stub(
        tmp_path,
        """
import subprocess
import sys
import time
from pathlib import Path

child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
Path(sys.argv[1]).write_text(str(child.pid), encoding="utf-8")
time.sleep(float(sys.argv[2]))
""",
    )
    session = _session_module()
    agent = session.AgentSession(
        [sys.executable, str(stub), str(pid_file), str(parent_delay)],
        [sys.executable, str(stub), str(pid_file), "0", "{thread_id}"],
        tmp_path,
        0.4,
    )

    result = agent.start("task")

    assert result.timed_out is timed_out
    child_pid = int(pid_file.read_text())
    _assert_pid_stopped(child_pid)
