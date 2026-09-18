"""F2: a hook cancelled at its timeout renders no decision.

The host discards a timed-out command hook's output, so a verifier allowed to
outlive the hook turns a blocking verdict into a silent pass. The verifier
deadline must sit strictly below the emitted hook timeout.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import theustad
from theustadlib import enrollment, hookadapter
from theustadlib.verifier import default_argv


ROOT = Path(__file__).resolve().parents[1]


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_ok.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    return repo


class _Stdin:
    def __init__(self, text):
        self._text = text

    def read(self):
        return self._text


def test_emitted_hook_config_carries_an_explicit_timeout():
    settings = theustad._claude_hook_settings(315.0)

    for event in ("SessionStart", "Stop"):
        entry = settings["hooks"][event][0]["hooks"][0]
        assert entry["type"] == "command"
        assert entry["timeout"] == 315


def test_emitted_timeout_is_rounded_up_never_down():
    entry = theustad._claude_hook_settings(30.2)["hooks"]["Stop"][0]["hooks"][0]

    assert entry["timeout"] == 31


def test_hook_timeout_defaults_to_the_verifier_deadline_plus_margin(tmp_path):
    policy = enrollment.Policy(repo=str(tmp_path), verifier_argv=("pytest",))

    assert policy.timeout == 300.0
    assert policy.hook_timeout == 300.0 + enrollment.MIN_HOOK_MARGIN


@pytest.mark.parametrize(
    ("timeout", "hook_timeout"),
    [(600.0, 600.0), (300.0, 310.0), (60.0, 30.0), (10.0, 10.0)],
)
def test_a_verifier_deadline_at_or_near_the_hook_timeout_is_refused(
    tmp_path, timeout, hook_timeout
):
    with pytest.raises(ValueError, match="renders no decision|render no decision"):
        enrollment.Policy(
            repo=str(tmp_path),
            verifier_argv=("pytest",),
            timeout=timeout,
            hook_timeout=hook_timeout,
        )


def test_hook_timeout_survives_a_policy_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    saved = enrollment.Policy(
        repo=str(repo),
        verifier_argv=tuple(default_argv()),
        timeout=60.0,
        hook_timeout=120.0,
    )
    enrollment.save_policy(saved)

    loaded = enrollment.load_policy(repo)

    assert loaded is not None
    assert loaded.hook_timeout == 120.0


def test_a_policy_written_before_hook_timeout_existed_still_loads(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    path = enrollment.save_policy(
        enrollment.Policy(repo=str(repo), verifier_argv=tuple(default_argv()))
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    del value["hook_timeout"]
    path.write_text(json.dumps(value), encoding="utf-8")

    loaded = enrollment.load_policy(repo)

    assert loaded is not None
    assert loaded.hook_timeout == loaded.timeout + enrollment.MIN_HOOK_MARGIN


def test_a_verifier_that_never_returns_blocks_well_before_the_hook_timeout(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setenv("THEUSTAD_HOME", str(tmp_path / "home"))
    repo = _repo(tmp_path)
    forever = tmp_path / "forever.py"
    forever.write_text("import time\ntime.sleep(3600)\n", encoding="utf-8")
    enrollment.save_policy(
        enrollment.Policy(
            repo=str(repo),
            verifier_argv=(sys.executable, str(forever)),
            timeout=2.0,
            hook_timeout=20.0,
        )
    )
    start = {
        "hook_event_name": "SessionStart",
        "session_id": "s-1",
        "cwd": str(repo),
        "source": "startup",
    }
    monkeypatch.setattr("sys.stdin", _Stdin(json.dumps(start)))
    assert hookadapter.main(["claude", "SessionStart"]) == hookadapter.ALLOW

    stop = {
        "hook_event_name": "Stop",
        "session_id": "s-1",
        "cwd": str(repo),
        "stop_hook_active": False,
        "last_assistant_message": "The task is complete.",
    }
    monkeypatch.setattr("sys.stdin", _Stdin(json.dumps(stop)))
    exit_code = hookadapter.main(["claude", "Stop"])

    assert exit_code == hookadapter.BLOCK
    assert hookadapter.HookVerdict.VERIFIER_TIMEOUT.value in capsys.readouterr().err


def _enroll(tmp_path, repo, *extra):
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "theustad.py"),
            "enroll",
            "--repo",
            str(repo),
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
        env={"THEUSTAD_HOME": str(tmp_path / "home"), "PATH": "/usr/bin:/bin"},
    )


def test_calibrate_refuses_an_unsafe_hook_timeout_without_enrolling(tmp_path):
    repo = _repo(tmp_path)
    slow = tmp_path / "slow.py"
    slow.write_text("import time\ntime.sleep(2)\n", encoding="utf-8")

    result = _enroll(
        tmp_path,
        repo,
        "--verifier",
        f"{Path(sys.executable).as_posix()} {slow.as_posix()}",
        # Fits its own deadline, but leaves under the margin below the hook
        # budget, so the host would cancel the hook and render no decision.
        "--timeout",
        "5",
        "--hook-timeout",
        "16",
        "--calibrate",
    )

    assert result.returncode == 2, result.stdout
    assert "needs a hook timeout of at least" in result.stderr
    assert not (tmp_path / "home" / "enrollments").exists()


def test_calibrate_accepts_a_fast_verifier_and_enrolls(tmp_path):
    repo = _repo(tmp_path)
    quick = tmp_path / "quick.py"
    quick.write_text("pass\n", encoding="utf-8")

    result = _enroll(
        tmp_path,
        repo,
        "--verifier",
        f"{Path(sys.executable).as_posix()} {quick.as_posix()}",
        "--timeout",
        "10",
        "--calibrate",
    )

    assert result.returncode == 0, result.stderr
    assert "CALIBRATE fits VERIFIER_DEADLINE 10s and HOOK_TIMEOUT 25s" in result.stdout
    assert "HOOK_TIMEOUT 25s" in result.stdout


def test_enroll_reports_both_deadlines_and_emits_the_timeout(tmp_path):
    repo = _repo(tmp_path)

    result = _enroll(tmp_path, repo, "--timeout", "45")

    assert result.returncode == 0, result.stderr
    assert "VERIFIER_DEADLINE 45s" in result.stdout
    assert "HOOK_TIMEOUT 60s" in result.stdout
    settings = json.loads(result.stdout[result.stdout.index("{") :])
    assert settings["hooks"]["Stop"][0]["hooks"][0]["timeout"] == 60


def test_calibrate_refuses_a_verifier_that_cannot_meet_its_own_deadline(tmp_path):
    """The hook budget is the outer bound; the verifier deadline is the real one."""
    repo = _repo(tmp_path)
    slow = tmp_path / "slow.py"
    slow.write_text("import time\ntime.sleep(1.2)\n", encoding="utf-8")

    result = _enroll(
        tmp_path,
        repo,
        "--verifier",
        f"{Path(sys.executable).as_posix()} {slow.as_posix()}",
        # Comfortably inside the hook budget, but past the verifier deadline:
        # every real Stop would time out and the run could never verify.
        "--timeout",
        "1",
        "--hook-timeout",
        "20",
        "--calibrate",
    )

    assert result.returncode == 2, result.stdout
    assert "does not fit the 1s verifier deadline" in result.stderr
    assert not (tmp_path / "home" / "enrollments").exists()


def test_calibrate_reports_a_timed_out_run(tmp_path):
    repo = _repo(tmp_path)
    slow = tmp_path / "slow.py"
    slow.write_text("import time\ntime.sleep(1.2)\n", encoding="utf-8")

    result = _enroll(
        tmp_path,
        repo,
        "--verifier",
        f"{Path(sys.executable).as_posix()} {slow.as_posix()}",
        "--timeout",
        "1",
        "--hook-timeout",
        "20",
        "--calibrate",
    )

    assert "TIMEOUT" in result.stdout, result.stdout


def test_calibrate_accepts_a_verifier_that_fits_both_budgets(tmp_path):
    repo = _repo(tmp_path)
    slow = tmp_path / "slow.py"
    slow.write_text("import time\ntime.sleep(1.2)\n", encoding="utf-8")

    result = _enroll(
        tmp_path,
        repo,
        "--verifier",
        f"{Path(sys.executable).as_posix()} {slow.as_posix()}",
        "--timeout",
        "5",
        "--hook-timeout",
        "25",
        "--calibrate",
    )

    assert result.returncode == 0, result.stderr
    assert "CALIBRATE fits VERIFIER_DEADLINE 5s and HOOK_TIMEOUT 25s" in result.stdout
