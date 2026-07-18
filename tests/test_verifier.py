import subprocess
import sys
import time
from pathlib import Path

import pytest


def _verifier():
    try:
        from gatelib import verifier
    except ImportError:
        pytest.fail("gatelib.verifier is not implemented", pytrace=False)
    return verifier


def test_default_argv_uses_absolute_isolated_python_and_defeats_pytest_shadowing(
    tmp_path,
):
    verifier = _verifier()
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pytest.py").write_text(
        'print("PLANTED PYTEST EXECUTED")\nraise SystemExit(0)\n',
        encoding="utf-8",
    )
    (repo / "test_real.py").write_text(
        "def test_real_failure():\n    assert False\n",
        encoding="utf-8",
    )

    argv = verifier.default_argv()
    result = verifier.run(argv, repo, timeout=30)

    assert Path(argv[0]).is_absolute()
    assert Path(argv[0]).resolve() == Path(sys.executable).resolve()
    assert argv[1:] == ["-I", "-m", "pytest", "-q"]
    assert result.exit_code != 0
    assert "1 failed" in result.output
    assert "PLANTED PYTEST EXECUTED" not in result.output


def test_run_passes_an_argv_list_with_shell_false(tmp_path, monkeypatch):
    verifier = _verifier()
    real_popen = subprocess.Popen
    observed = {}

    def recording_popen(*args, **kwargs):
        observed["argv"] = args[0]
        observed["shell"] = kwargs.get("shell")
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(verifier.subprocess, "Popen", recording_popen)
    argv = [sys.executable, "-c", "print('trusted argv')"]

    result = verifier.run(argv, tmp_path)

    assert observed == {"argv": argv, "shell": False}
    assert result.exit_code == 0
    assert result.output.strip() == "trusted argv"


def test_custom_command_uses_shlex_and_rejects_shell_operators():
    verifier = _verifier()

    assert verifier.parse_command('python -m pytest -q "tests/unit tests"') == [
        "python",
        "-m",
        "pytest",
        "-q",
        "tests/unit tests",
    ]

    for command in (
        "pytest -q | tee result.txt",
        "pytest -q > result.txt",
        "pytest -q && echo pass",
        "pytest -q; echo pass",
    ):
        with pytest.raises(ValueError, match="shell operators"):
            verifier.parse_command(command)

    with pytest.raises(ValueError, match="empty"):
        verifier.parse_command("   ")


def test_run_merges_output_and_retains_only_last_thirty_lines(tmp_path):
    verifier = _verifier()
    code = """
import sys
for number in range(35):
    stream = sys.stderr if number % 2 else sys.stdout
    print(f"line {number}", file=stream, flush=True)
"""

    result = verifier.run([sys.executable, "-c", code], tmp_path)

    expected = [f"line {number}" for number in range(35)]
    assert result.exit_code == 0
    assert result.output.splitlines() == expected
    assert result.tail == tuple(expected[-30:])
    assert result.warning is None


def test_timeout_returns_124_with_explicit_evidence(tmp_path):
    verifier = _verifier()
    started = time.monotonic()

    result = verifier.run(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        tmp_path,
        timeout=0.2,
    )

    assert time.monotonic() - started < 3
    assert result.exit_code == 124
    assert result.timed_out is True
    assert result.tail[-1] == "VERIFIER_TIMEOUT after 0.2 seconds"
    assert result.warning == "VERIFIER_TIMEOUT after 0.2 seconds"


def test_empty_output_is_exposed_as_a_warning(tmp_path):
    verifier = _verifier()

    result = verifier.run([sys.executable, "-c", "pass"], tmp_path)

    assert result.exit_code == 0
    assert result.output == ""
    assert result.tail == ()
    assert result.warning == "Verifier produced no output."
