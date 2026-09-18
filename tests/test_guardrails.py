"""Guardrails against silently meaningless runs and audits."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import theustad
from theustadlib.chain import AuditChain, verify


ROOT = Path(__file__).resolve().parents[1]
VERIFY_CHAIN = ROOT / "verify_chain.py"


def _agent_script(tmp_path: Path) -> Path:
    script = tmp_path / "agent.py"
    script.write_text(
        "import json\n"
        'print(json.dumps({"type": "thread.started", "thread_id": "t-1"}), flush=True)\n'
        "print(json.dumps({\n"
        '    "type": "item.completed",\n'
        '    "item": {"type": "agent_message", "text": "The task is complete."},\n'
        "}), flush=True)\n",
        encoding="utf-8",
    )
    return script


def test_run_warns_loudly_when_no_protected_input_matches(tmp_path):
    repo = tmp_path / "repo"
    # Tests live in spec/, which none of the default patterns cover.
    (repo / "spec").mkdir(parents=True)
    (repo / "spec" / "test_x.py").write_text(
        "def test_x():\n    assert True\n", encoding="utf-8"
    )
    state = tmp_path / "state"

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "theustad.py"),
            "--repo",
            str(repo),
            "--task",
            "Do the work.",
            "--cmd",
            f"{sys.executable} {_agent_script(tmp_path)}",
            "--resume-cmd",
            f"{sys.executable} {_agent_script(tmp_path)} {{thread_id}}",
            "--verifier",
            f"{sys.executable} -B -m pytest -q spec",
            "--max-retries",
            "0",
            "--state-dir",
            str(state),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )

    assert "PROTECTED 0 paths" in result.stdout, result.stdout
    assert theustad.NO_PROTECTED_INPUTS in result.stdout
    assert "FINAL VERIFIED" in result.stdout

    log = sorted((state / "logs").glob("audit_*.jsonl"))[-1]
    warnings = [
        json.loads(line)
        for line in log.read_text(encoding="utf-8").splitlines()
        if json.loads(line)["kind"] == "warning"
    ]
    assert any(
        record["data"]["message"] == theustad.NO_PROTECTED_INPUTS
        for record in warnings
    ), warnings


def test_run_reports_the_protected_path_count(tmp_path):
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_x.py").write_text(
        "def test_x():\n    assert True\n", encoding="utf-8"
    )

    lines: list[str] = []
    runner = theustad.TheUstadRunner(
        repo=repo,
        task="Do the work.",
        session=theustad.AgentSession(
            [sys.executable, str(_agent_script(tmp_path))],
            [sys.executable, str(_agent_script(tmp_path))],
            repo,
            30,
        ),
        verifier_argv=[sys.executable, "-I", "-B", "-m", "pytest", "-q"],
        patterns=theustad.DEFAULT_PATTERNS,
        state_dir=tmp_path / "state",
        log_dir=tmp_path / "logs",
        max_retries=0,
        timeout=30,
        output=lines.append,
    )
    runner.run()

    assert "PROTECTED 2 paths" in lines
    assert theustad.NO_PROTECTED_INPUTS not in lines


@pytest.mark.parametrize(
    "value",
    ["tasks/ticket-4127.md", "./missing.md", "ticket.txt", "notes/plan.rst"],
)
def test_missing_task_file_fails_instead_of_becoming_the_prompt(value):
    with pytest.raises(ValueError, match="task file not found"):
        theustad._task_text(value)


@pytest.mark.parametrize(
    "value",
    [
        "Fix parse_duration so that 90m returns 5400.",
        "Implement the invoice validator.",
        "refactor",
    ],
)
def test_inline_task_text_is_still_accepted(value):
    assert theustad._task_text(value) == value


def test_existing_task_file_is_read(tmp_path):
    task = tmp_path / "task.md"
    task.write_text("Fix ticket 4127.\n", encoding="utf-8")

    assert theustad._task_text(str(task)) == "Fix ticket 4127.\n"


def _oracle(path):
    return subprocess.run(
        [sys.executable, str(VERIFY_CHAIN), str(path)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_empty_audit_chain_is_broken_in_both_oracles(tmp_path):
    log = tmp_path / "audit_empty.jsonl"
    log.write_text("", encoding="utf-8")

    result = _oracle(log)

    assert result.returncode == 1
    assert result.stdout.strip() == "BROKEN at seq 0: audit chain is empty"
    with pytest.raises(ValueError, match="audit chain is empty"):
        verify(log)


def test_truncated_audit_chain_is_broken(tmp_path):
    chain = AuditChain(tmp_path)
    for index in range(3):
        chain.append(round_number=1, kind="verdict", data={"value": index})
    chain.path.write_text("", encoding="utf-8")

    assert _oracle(chain.path).returncode == 1


def test_malformed_records_report_broken_rather_than_a_traceback(tmp_path):
    cases = {
        "not-json.jsonl": "this is not json\n",
        "not-object.jsonl": "[1, 2, 3]\n",
        "no-hash.jsonl": json.dumps({"seq": 0, "prev": "0" * 64}) + "\n",
    }
    for name, content in cases.items():
        log = tmp_path / name
        log.write_text(content, encoding="utf-8")

        result = _oracle(log)

        assert result.returncode == 1, name
        assert result.stdout.startswith("BROKEN at seq 0: "), (name, result.stdout)
        assert "Traceback" not in result.stderr, name


def test_reordered_sequence_numbers_are_broken(tmp_path):
    chain = AuditChain(tmp_path)
    for index in range(3):
        chain.append(round_number=1, kind="verdict", data={"value": index})
    records = [
        json.loads(line) for line in chain.path.read_text(encoding="utf-8").splitlines()
    ]
    records[1]["seq"] = 7
    chain.path.write_text(
        "".join(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )

    result = _oracle(chain.path)

    assert result.returncode == 1
    assert result.stdout.strip().startswith("BROKEN at seq 1:")


def test_unreadable_audit_chain_reports_an_error_not_a_traceback(tmp_path):
    result = _oracle(tmp_path / "does-not-exist.jsonl")

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.startswith("ERROR cannot read audit chain:")
    assert "Traceback" not in result.stderr
