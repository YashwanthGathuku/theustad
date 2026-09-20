"""A launcher can remove the variable TheUstad sets, before Python starts."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from theustadlib.verifier import parse_command, strips_bytecode_environment

# The rule under test is about POSIX launchers, and so is the evidence for
# it.  Windows ships an MSYS env.EXE with Git, but it rewrites arguments on
# its way to a native interpreter, which makes it an unreliable witness to
# what plain coreutils env does.  The parse-side guard is checked everywhere.
POSIX_ENV = shutil.which("env") if os.name == "posix" else None


@pytest.mark.parametrize(
    "command",
    [
        "/usr/bin/env -u PYTHONDONTWRITEBYTECODE {python} -m pytest -q",
        "/usr/bin/env --unset=PYTHONDONTWRITEBYTECODE {python} -m pytest",
        "/usr/bin/env -i {python} -m pytest -q",
        "/usr/bin/env --ignore-environment {python} -m pytest",
    ],
)
def test_a_launcher_that_strips_the_variable_is_refused(command):
    with pytest.raises(ValueError, match="isolated Python|PYTHONDONTWRITEBYTECODE"):
        parse_command(command.format(python=Path(sys.executable).as_posix()))


@pytest.mark.parametrize(
    "command",
    [
        "/usr/bin/env -u SOMETHING_ELSE {python} -m pytest -q",
        "/usr/bin/env -i {python} -B -m pytest -q",
        "/usr/bin/env {python} -m pytest -q",
        "/usr/bin/env FOO=bar {python} -m pytest",
    ],
)
def test_a_launcher_that_leaves_it_alone_is_accepted(command):
    assert parse_command(command.format(python=Path(sys.executable).as_posix()))


def _environment_that_forbids_bytecode() -> dict[str, str]:
    """Keep what the OS needs to start Python, drop what else steers bytecode."""
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("PYTHON")
    }
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


@pytest.mark.skipif(POSIX_ENV is None, reason="no POSIX env launcher here")
def test_env_u_really_removes_the_variable(tmp_path):
    """Ground the rule in observed behaviour, not in how the flag reads."""
    protected = tmp_path / "tests"
    protected.mkdir()
    (protected / "probe_mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    code = f"import sys; sys.path.insert(0, {str(protected)!r}); import probe_mod"

    subprocess.run(
        [
            POSIX_ENV,
            "-u",
            "PYTHONDONTWRITEBYTECODE",
            sys.executable,
            "-c",
            code,
        ],
        capture_output=True,
        check=True,
        env=_environment_that_forbids_bytecode(),
    )

    assert (protected / "__pycache__").exists(), (
        "expected the stripped variable to let bytecode into the protected tree"
    )


def test_the_scan_stops_at_the_interpreter():
    """A -u after the interpreter belongs to the program, not the launcher."""
    argv = ["/usr/bin/env", "python", "-m", "pytest", "-u", "PYTHONDONTWRITEBYTECODE"]

    assert strips_bytecode_environment(argv, 1) is False
