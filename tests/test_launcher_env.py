"""A launcher can defeat the variable TheUstad sets, before Python starts."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from theustadlib.verifier import (
    BYTECODE_VARIABLE,
    overrides_bytecode_environment,
    parse_command,
)

# The rules under test are about POSIX launchers, and so is the evidence for
# them.  Windows ships an MSYS env.EXE with Git, but it rewrites arguments on
# its way to a native interpreter, which makes it an unreliable witness to
# what plain coreutils env does.  The parse-side guard is checked everywhere.
POSIX_ENV = shutil.which("env") if os.name == "posix" else None

# Each spelling reaches Python without a suppressing PYTHONDONTWRITEBYTECODE:
# -i and a bare - clear the environment, -u and --unset drop the variable, and
# an assignment overrides it with a value CPython reads as off.
DEFEATS = (
    "-u PYTHONDONTWRITEBYTECODE",
    "-uPYTHONDONTWRITEBYTECODE",
    "--unset PYTHONDONTWRITEBYTECODE",
    "--unset=PYTHONDONTWRITEBYTECODE",
    "-i",
    "--ignore-environment",
    "-",
    "-iu SOMETHING_ELSE",
    "PYTHONDONTWRITEBYTECODE=",
    "PYTHONDONTWRITEBYTECODE=0",
)

# Each of these leaves the variable alone: -u and an assignment naming some
# other variable, and -- which only ends option parsing.
LEAVES_IT_ALONE = (
    "-u SOMETHING_ELSE",
    "-uSOMETHING_ELSE",
    "--unset=SOMETHING_ELSE",
    "FOO=bar",
    "--",
    "",
)


@pytest.mark.parametrize("launcher", DEFEATS)
def test_a_launcher_that_defeats_the_variable_is_refused(launcher):
    python = Path(sys.executable).as_posix()

    with pytest.raises(ValueError, match="isolated Python|PYTHONDONTWRITEBYTECODE"):
        parse_command(f"env {launcher} {python} -m pytest -q")


@pytest.mark.parametrize("launcher", LEAVES_IT_ALONE)
def test_a_launcher_that_leaves_it_alone_is_accepted(launcher):
    python = Path(sys.executable).as_posix()

    assert parse_command(f"env {launcher} {python} -m pytest -q")


@pytest.mark.parametrize("launcher", DEFEATS)
def test_suppressing_the_writes_makes_the_launcher_safe_again(launcher):
    """-B is a command-line option, so no launcher can take it away."""
    python = Path(sys.executable).as_posix()

    assert parse_command(f"env {launcher} {python} -B -m pytest -q")


@pytest.mark.parametrize(
    "command",
    [
        "env -S'-i {python} -m pytest -q'",
        "env --split-string='-i {python} -m pytest'",
        "env -S'{python} -m pytest'",
    ],
)
def test_a_launcher_that_hides_the_command_is_refused(command):
    """The interpreter is inside the string, so every other check misses it."""
    python = Path(sys.executable).as_posix()

    with pytest.raises(ValueError, match="packs the whole command"):
        parse_command(command.format(python=python))


def test_the_scan_stops_at_the_interpreter():
    """A -u after the interpreter belongs to the program, not the launcher."""
    argv = ["env", "python", "-m", "pytest", "-u", BYTECODE_VARIABLE]

    assert overrides_bytecode_environment(argv, 1) is False


def _environment_that_forbids_bytecode() -> dict[str, str]:
    """Keep what the OS needs to start Python, drop what else steers bytecode."""
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("PYTHON")
    }
    environment[BYTECODE_VARIABLE] = "1"
    return environment


def _writes_bytecode(tmp_path: Path, launcher: list[str]) -> bool:
    """Run a real interpreter behind a real env and look for the bytecode."""
    protected = tmp_path / "tests"
    protected.mkdir()
    (protected / "probe_mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    code = f"import sys; sys.path.insert(0, {str(protected)!r}); import probe_mod"

    subprocess.run(
        [POSIX_ENV, *launcher, sys.executable, "-c", code],
        capture_output=True,
        check=True,
        env=_environment_that_forbids_bytecode(),
    )
    return (protected / "__pycache__").exists()


@pytest.mark.skipif(POSIX_ENV is None, reason="no POSIX env launcher here")
@pytest.mark.parametrize("launcher", DEFEATS)
def test_each_refused_spelling_really_defeats_the_variable(tmp_path, launcher):
    """Ground the rule in observed behaviour, not in how the flags read."""
    assert _writes_bytecode(tmp_path, launcher.split()), (
        f"{launcher!r} was refused but leaves the suppression in place, so the "
        "rule refuses a verifier that would have been honest"
    )


@pytest.mark.skipif(POSIX_ENV is None, reason="no POSIX env launcher here")
@pytest.mark.parametrize("launcher", LEAVES_IT_ALONE)
def test_each_accepted_spelling_really_leaves_it_alone(tmp_path, launcher):
    """The other half of the rule: accepting these has to stay safe."""
    assert not _writes_bytecode(tmp_path, launcher.split()), (
        f"{launcher!r} is accepted but lets bytecode into the protected tree, "
        "so an honest run would be reported as TAMPERED"
    )


@pytest.mark.skipif(POSIX_ENV is None, reason="no POSIX env launcher here")
def test_a_redundant_assignment_is_refused_although_it_is_harmless(tmp_path):
    """A deliberate over-refusal, named here so it is a choice, not a gap.

    PYTHONDONTWRITEBYTECODE=1 leaves the suppression in place, so refusing it
    turns away a verifier that would have been honest.  Telling it apart from
    =0 and = means reproducing CPython's integer parsing, where -1 and 'no'
    both count as on and 0 and '' do not; getting that wrong the other way
    reports an honest run as TAMPERED.  TheUstad already sets the variable, so
    the assignment buys nothing, and the message says to drop it.
    """
    assert not _writes_bytecode(tmp_path, [f"{BYTECODE_VARIABLE}=1"])

    python = Path(sys.executable).as_posix()
    with pytest.raises(ValueError, match="drop it"):
        parse_command(f"env {BYTECODE_VARIABLE}=1 {python} -m pytest -q")
