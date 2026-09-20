"""F7 in hook mode: the Stop verdict has to require the tests to have run.

The wrapper CLI and the hook interface reach the same verdicts by different
code, and the census was wired into one of them.  Both attacks below reached
VERIFIED through Stop while add() returned a - b, because the Stop verdict
read only the verifier's exit code.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


CLI = Path(__file__).resolve().parents[1] / "theustad.py"

HONEST = "def add(a, b):\n    return a + b\n"
BROKEN = "def add(a, b):\n    return a - b\n"
T6_MODULE_SKIP = (
    'import pytest\n\npytest.skip("unsupported", allow_module_level=True)\n\n\n'
    "def add(a, b):\n    return a - b\n"
)
T7_EXIT = "import os\n\nos._exit(0)\n\n\ndef add(a, b):\n    return a - b\n"
CLAIM = "The fix is complete and all tests pass."


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "app").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n", encoding="utf-8")
    (repo / "app" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "app" / "calc.py").write_text(HONEST, encoding="utf-8")
    # Named so that a `-k python` verifier still selects it: that spelling
    # makes a pytest argument look like an interpreter to the flag scanner.
    (repo / "tests" / "test_calc.py").write_text(
        "from app.calc import add\n\n\ndef test_python_add():\n"
        "    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    # A second module that keeps passing, so the suite stays green when the
    # first one is removed from collection.
    (repo / "tests" / "test_other.py").write_text(
        "def test_unrelated():\n    assert True\n", encoding="utf-8"
    )
    return repo


class _Session:
    """Drive one enrolled repository through SessionStart and Stop."""

    def __init__(
        self, tmp_path: Path, *enroll_args: str, extra: dict[str, str] | None = None
    ):
        # enroll_args are passed through, so a caller can name its own verifier.
        self.repo = _repo(tmp_path)
        for name, source in (extra or {}).items():
            (self.repo / "tests" / name).write_text(source, encoding="utf-8")
        self.home = tmp_path / "external"
        self.env = {**os.environ, "THEUSTAD_HOME": str(self.home)}
        assert self._run("enroll", "--repo", str(self.repo), *enroll_args).returncode == 0
        assert self._hook("SessionStart", self._start()).returncode == 0

    def _run(self, *args, payload=None):
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            input=None if payload is None else json.dumps(payload),
            capture_output=True,
            text=True,
            env=self.env,
            check=False,
        )

    def _hook(self, event, payload):
        return self._run("hook", "claude", event, payload=payload)

    def _start(self):
        return {
            "session_id": "census-session",
            "transcript_path": "/tmp/transcript.jsonl",
            "cwd": str(self.repo),
            "hook_event_name": "SessionStart",
            "source": "startup",
        }

    def stop(self, source: str, message: str = CLAIM):
        (self.repo / "app" / "calc.py").write_text(source, encoding="utf-8")
        return self._hook(
            "Stop",
            {
                "session_id": "census-session",
                "transcript_path": "/tmp/transcript.jsonl",
                "cwd": str(self.repo),
                "permission_mode": "default",
                "hook_event_name": "Stop",
                "stop_hook_active": False,
                "last_assistant_message": message,
                "background_tasks": [],
                "session_crons": [],
            },
        )

    def audit(self):
        log = next(self.home.rglob("*.jsonl"))
        return [json.loads(line) for line in log.read_text().splitlines()]

    def chain_is_valid(self):
        return self._run("verify-chain", "--repo", str(self.repo)).returncode == 0


@pytest.mark.parametrize(
    ("label", "source"),
    [("module-level skip", T6_MODULE_SKIP), ("exit during import", T7_EXIT)],
)
def test_a_green_exit_without_the_tests_is_not_verified(tmp_path, label, source):
    session = _Session(tmp_path)

    response = session.stop(source)

    assert response.returncode == 2, f"{label} reached a passing Stop"
    assert "FALSIFIED" in response.stderr
    assert "does not show the acceptance tests running" in response.stderr
    assert session.chain_is_valid()


def test_the_census_is_what_catches_it(tmp_path):
    """Without the census the same attack passes, which is what makes it the cause."""
    session = _Session(tmp_path, "--no-census")

    response = session.stop(T7_EXIT)

    assert response.returncode == 0
    assert "VERIFIED" in response.stdout


def test_an_honest_repository_still_verifies(tmp_path):
    session = _Session(tmp_path)

    response = session.stop(HONEST)

    assert response.returncode == 0, response.stderr
    assert "VERIFIED" in response.stdout


def test_a_plainly_broken_repository_is_falsified_on_the_evidence(tmp_path):
    """The census must not be the only thing standing between green and red."""
    session = _Session(tmp_path)

    response = session.stop(BROKEN)

    assert response.returncode == 2
    assert "FALSIFIED" in response.stderr
    assert "does not show the acceptance tests running" not in response.stderr


def test_the_baseline_is_recorded_in_the_audit_at_session_start(tmp_path):
    session = _Session(tmp_path)

    start = next(
        record
        for record in session.audit()
        if record["data"].get("event") == "session_start"
    )

    assert start["data"]["census"] == {"armed": True, "tests": 2, "detail": ""}


def test_the_finding_names_itself_in_the_audit(tmp_path):
    session = _Session(tmp_path)
    session.stop(T6_MODULE_SKIP)

    verdict = next(
        record for record in session.audit() if record["kind"] == "verdict"
    )

    assert verdict["data"]["census"] == "CENSUS_SHRINK"
    assert verdict["data"]["verifier_exit_code"] == 0


def test_a_disabled_census_is_recorded_as_such_at_session_start(tmp_path):
    session = _Session(tmp_path, "--no-census")

    start = next(
        record
        for record in session.audit()
        if record["data"].get("event") == "session_start"
    )

    assert start["data"]["census"]["armed"] is False


def test_a_test_the_repository_itself_skips_is_not_a_finding(tmp_path):
    """What makes the rule safe to enforce: a real skip is the repo's choice."""
    session = _Session(
        tmp_path,
        extra={
            "test_skipped.py": (
                'import pytest\n\n\n@pytest.mark.skip("not ready")\n'
                "def test_later():\n    assert False\n"
            )
        },
    )

    response = session.stop(HONEST)

    assert response.returncode == 0, response.stderr
    assert "VERIFIED" in response.stdout


def test_a_verifier_that_is_not_pytest_stands_down_rather_than_blocking(tmp_path):
    python = Path(sys.executable).as_posix()
    session = _Session(tmp_path, "--verifier", f"{python} -B -c pass")

    response = session.stop(T7_EXIT)

    start = next(
        record
        for record in session.audit()
        if record["data"].get("event") == "session_start"
    )
    assert start["data"]["census"]["detail"] == "not supervising"
    # Standing down means this verifier's own answer decides, as before.
    assert response.returncode == 0


def test_a_compaction_cannot_rebaseline_the_census(tmp_path):
    """Otherwise the attack is: plant the skip, compact, get a shrunken baseline."""
    session = _Session(tmp_path)
    (session.repo / "app" / "calc.py").write_text(T6_MODULE_SKIP, encoding="utf-8")

    reentry = session._hook(
        "SessionStart",
        {**session._start(), "source": "compact"},
    )
    response = session.stop(T6_MODULE_SKIP)

    assert reentry.returncode == 0, reentry.stderr
    assert response.returncode == 2
    assert "does not show the acceptance tests running" in response.stderr


def test_a_verified_round_does_not_leave_its_report_for_the_next_one(tmp_path):
    """A VERIFIED round resets the blocks, so the next Stop is round 1 again.

    The report path is derived from the round number, so without clearing it
    the second Stop reads the first round's passing report -- and the attack
    that dies before pytest writes anything is exactly the one that benefits.
    """
    session = _Session(tmp_path)
    first = session.stop(HONEST)

    second = session.stop(T7_EXIT)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 2, "the attack reused the honest round's report"
    assert "does not show the acceptance tests running" in second.stderr


@pytest.mark.parametrize(
    ("label", "verifier"),
    [
        ("attached -m", "{python} -B -mpytest -q"),
        ("clustered -m", "{python} -Bmpytest -q"),
        ("path separator", "{python} -B -m pytest -q -- tests"),
        ("launcher separator", "env -- {python} -B -m pytest -q"),
        ("both separators", "env -- {python} -B -m pytest -q -- tests"),
        ("path named like python", "{python} -B -m pytest -q -k python"),
    ],
)
def test_pytest_is_supervised_however_the_verifier_spells_it(
    tmp_path, label, verifier
):
    """An unrecognised spelling stands the census down without saying so."""
    python = Path(sys.executable).as_posix()
    session = _Session(tmp_path, "--verifier", verifier.format(python=python))

    response = session.stop(T7_EXIT)

    assert response.returncode == 2, f"{label} left the verifier unsupervised"
    assert "does not show the acceptance tests running" in response.stderr
