import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


VERIFY_CHAIN = Path(__file__).parents[1] / "verify_chain.py"


def _theustad():
    try:
        import theustad
    except ModuleNotFoundError:
        pytest.fail("theustad.py is not implemented", pytrace=False)
    return theustad


class ScriptedSession:
    def __init__(self, results, actions=None):
        self.results = list(results)
        self.actions = list(actions or [None] * len(self.results))
        self.start_tasks = []
        self.resume_messages = []

    def _next(self):
        action = self.actions.pop(0)
        if action is not None:
            action()
        return self.results.pop(0)

    def start(self, task, *, on_line=None):
        self.start_tasks.append(task)
        return self._next()

    def resume(self, message, *, on_line=None):
        self.resume_messages.append(message)
        return self._next()


def _agent_result(
    message,
    *,
    exit_code=0,
    timed_out=False,
    warnings=(),
):
    return SimpleNamespace(
        argv=("agent",),
        exit_code=exit_code,
        timed_out=timed_out,
        thread_id="thread-exact",
        last_agent_message=message,
        non_json_tail=(),
        warnings=warnings,
    )


def _verification_result(exit_code=0, *, tail=("verifier evidence",)):
    return SimpleNamespace(
        argv=(sys.executable, "-I", "-m", "pytest", "-q"),
        exit_code=exit_code,
        output="\n".join(tail),
        tail=tail,
        timed_out=exit_code == 124,
        warning=None,
    )


@pytest.fixture
def protected_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "app").mkdir()
    (repo / "tests" / "test_trusted.py").write_text(
        "def test_trusted():\n    assert True\n",
        encoding="utf-8",
    )
    (repo / "app" / "code.py").write_text("VALUE = 1\n", encoding="utf-8")
    return repo


def _run_theustad(
    theustad,
    repo,
    session,
    verifier_runner,
    *,
    max_retries=0,
    claim_finder=None,
):
    output = []
    kwargs = {}
    if claim_finder is not None:
        kwargs["claim_finder"] = claim_finder
    runner = theustad.TheUstadRunner(
        repo=repo,
        task="implement the task",
        session=session,
        verifier_argv=[sys.executable, "-I", "-m", "pytest", "-q"],
        patterns=("tests/**",),
        state_dir=repo.parent / "state",
        log_dir=repo.parent / "logs",
        max_retries=max_retries,
        timeout=2,
        verifier_runner=verifier_runner,
        output=output.append,
        **kwargs,
    )
    return runner.run(), output


@pytest.mark.parametrize(
    ("message", "verifier_exit", "expected", "expected_exit"),
    [
        ("The task is complete.", 0, "VERIFIED", 0),
        ("The task is complete.", 1, "FALSIFIED", 1),
        ("I am still working on it.", 0, "PASS_NO_CLAIM", 1),
        ("I am still working on it.", 1, "INCOMPLETE", 1),
    ],
)
def test_verdict_matrix_and_only_verified_exits_zero(
    protected_repo,
    message,
    verifier_exit,
    expected,
    expected_exit,
):
    theustad = _theustad()
    session = ScriptedSession([_agent_result(message)])
    verifier_calls = []

    def run_verifier(argv, repo, timeout):
        verifier_calls.append((tuple(argv), Path(repo), timeout))
        return _verification_result(verifier_exit)

    result, _ = _run_theustad(theustad, protected_repo, session, run_verifier)

    assert result.verdict.value == expected
    assert result.exit_code == expected_exit
    assert [round_result.verdict.value for round_result in result.rounds] == [
        expected
    ]
    assert len(verifier_calls) == 1


@pytest.mark.parametrize(
    ("agent_result", "expected"),
    [
        (_agent_result("The task is complete.", exit_code=2), "AGENT_ERROR"),
        (
            _agent_result("The task is complete.", exit_code=124, timed_out=True),
            "AGENT_TIMEOUT",
        ),
    ],
)
def test_agent_failure_precedes_claims_and_stale_green_verifier(
    protected_repo,
    agent_result,
    expected,
):
    theustad = _theustad()
    session = ScriptedSession([agent_result])

    def stale_green(*args, **kwargs):
        pytest.fail("verifier must not run after an agent failure")

    result, _ = _run_theustad(theustad, protected_repo, session, stale_green)

    assert result.verdict.value == expected
    assert result.exit_code != 0


def test_post_agent_tampering_precedes_claims_and_verifier_and_is_restored(
    protected_repo,
):
    theustad = _theustad()
    trusted_test = protected_repo / "tests" / "test_trusted.py"
    baseline = trusted_test.read_text(encoding="utf-8")
    session = ScriptedSession(
        [_agent_result("The task is complete.")],
        actions=[lambda: trusted_test.write_text("assert False\n", encoding="utf-8")],
    )

    def stale_green(*args, **kwargs):
        pytest.fail("verifier must not run after agent tampering")

    result, _ = _run_theustad(theustad, protected_repo, session, stale_green)

    assert result.verdict.value == "TAMPERED"
    assert result.exit_code != 0
    assert trusted_test.read_text(encoding="utf-8") == baseline
    assert result.rounds[0].tampering.modified == ["tests/test_trusted.py"]


def test_pre_verifier_manifest_check_blocks_new_tampering(protected_repo):
    theustad = _theustad()
    trusted_test = protected_repo / "tests" / "test_trusted.py"
    baseline = trusted_test.read_text(encoding="utf-8")
    session = ScriptedSession([_agent_result("The task is complete.")])

    def mutate_while_classifying(text):
        trusted_test.write_text("assert False\n", encoding="utf-8")
        return [SimpleNamespace(sentence=text, phrases=["complete"])]

    def stale_green(*args, **kwargs):
        pytest.fail("verifier must not run after pre-verifier tampering")

    result, _ = _run_theustad(
        theustad,
        protected_repo,
        session,
        stale_green,
        claim_finder=mutate_while_classifying,
    )

    assert result.verdict.value == "TAMPERED"
    assert trusted_test.read_text(encoding="utf-8") == baseline


def test_post_verifier_race_tampering_overrides_green_verifier(protected_repo):
    theustad = _theustad()
    trusted_test = protected_repo / "tests" / "test_trusted.py"
    baseline = trusted_test.read_text(encoding="utf-8")
    session = ScriptedSession([_agent_result("The task is complete.")])

    def racing_verifier(argv, repo, timeout):
        trusted_test.write_text("assert False\n", encoding="utf-8")
        return _verification_result(0, tail=("1 passed",))

    result, _ = _run_theustad(theustad, protected_repo, session, racing_verifier)

    assert result.verdict.value == "TAMPERED"
    assert result.exit_code != 0
    assert result.rounds[0].verification.exit_code == 0
    assert trusted_test.read_text(encoding="utf-8") == baseline


def test_manifest_checks_immediately_follow_agent_and_verifier(
    protected_repo,
    monkeypatch,
):
    theustad = _theustad()
    order = []
    session = ScriptedSession(
        [_agent_result("The task is complete.")],
        actions=[lambda: order.append("agent_return")],
    )
    real_check = theustad.check
    real_append = theustad.AuditChain.append

    def ordered_check(repo, manifest):
        order.append("manifest_check")
        return real_check(repo, manifest)

    def ordered_append(audit, *, round_number, kind, data):
        if kind == "session":
            order.append("session_log")
        elif kind == "warning" and data["message"] == "verifier warning":
            order.append("verifier_warning_log")
        return real_append(
            audit,
            round_number=round_number,
            kind=kind,
            data=data,
        )

    def ordered_verifier(argv, repo, timeout):
        order.append("verifier_return")
        result = _verification_result(0)
        result.warning = "verifier warning"
        return result

    monkeypatch.setattr(theustad, "check", ordered_check)
    monkeypatch.setattr(theustad.AuditChain, "append", ordered_append)

    _run_theustad(theustad, protected_repo, session, ordered_verifier)

    assert order == [
        "agent_return",
        "manifest_check",
        "session_log",
        "manifest_check",
        "verifier_return",
        "manifest_check",
        "verifier_warning_log",
    ]


def test_tamper_resume_lists_files_and_requires_code_fix(protected_repo):
    theustad = _theustad()
    trusted_test = protected_repo / "tests" / "test_trusted.py"
    baseline = trusted_test.read_text(encoding="utf-8")

    def assert_restored_before_resume():
        assert trusted_test.read_text(encoding="utf-8") == baseline

    session = ScriptedSession(
        [
            _agent_result("The task is complete."),
            _agent_result("The task is complete."),
        ],
        actions=[
            lambda: trusted_test.write_text("assert False\n", encoding="utf-8"),
            assert_restored_before_resume,
        ],
    )

    result, _ = _run_theustad(
        theustad,
        protected_repo,
        session,
        lambda argv, repo, timeout: _verification_result(0),
        max_retries=1,
    )

    assert [item.verdict.value for item in result.rounds] == [
        "TAMPERED",
        "VERIFIED",
    ]
    assert "tests/test_trusted.py" in session.resume_messages[0]
    assert "fix code rather than trusted tests" in session.resume_messages[0]


def test_pass_no_claim_resumes_only_once_and_remains_non_successful(
    protected_repo,
):
    theustad = _theustad()
    session = ScriptedSession(
        [
            _agent_result("I am still working on it."),
            _agent_result("No explicit completion status."),
        ]
    )

    result, _ = _run_theustad(
        theustad,
        protected_repo,
        session,
        lambda argv, repo, timeout: _verification_result(0),
        max_retries=3,
    )

    assert [item.verdict.value for item in result.rounds] == [
        "PASS_NO_CLAIM",
        "PASS_NO_CLAIM",
    ]
    assert result.exit_code != 0
    assert len(session.resume_messages) == 1
    assert "explicit completion status" in session.resume_messages[0]


def test_final_record_root_is_printed_and_valid(protected_repo):
    theustad = _theustad()
    session = ScriptedSession([_agent_result("The task is complete.")])

    result, output = _run_theustad(
        theustad,
        protected_repo,
        session,
        lambda argv, repo, timeout: _verification_result(0),
    )
    records = [json.loads(line) for line in result.log_path.read_text().splitlines()]
    verified = subprocess.run(
        [sys.executable, str(VERIFY_CHAIN), str(result.log_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert records[-1]["kind"] == "final"
    assert records[-1]["data"]["verdict"] == "VERIFIED"
    assert result.root == records[-1]["hash"]
    assert verified.returncode == 0
    assert f"AUDIT_ROOT {result.root}" in output
    assert any("pushed Git commit and submission text" in line for line in output)
