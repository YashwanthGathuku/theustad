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


def _writes_bytecode(tmp_path: Path, launcher: list[str]) -> bool | None:
    """Run a real interpreter behind a real env and look for the bytecode.

    ``None`` means this env could not run that spelling at all.  Not every
    env is coreutils: BSD env, which is what macOS ships, has none of the
    GNU long options, so ``--unset NAME`` is read as the command to run.  A
    spelling that cannot run cannot defeat anything, and refusing it costs
    nothing, so there is nothing to observe rather than something to assert.
    """
    protected = tmp_path / "tests"
    protected.mkdir()
    (protected / "probe_mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    code = f"import sys; sys.path.insert(0, {str(protected)!r}); import probe_mod"

    probe = subprocess.run(
        [POSIX_ENV, *launcher, sys.executable, "-c", code],
        capture_output=True,
        check=False,
        env=_environment_that_forbids_bytecode(),
    )
    if probe.returncode != 0:
        return None
    return (protected / "__pycache__").exists()


@pytest.mark.skipif(POSIX_ENV is None, reason="no POSIX env launcher here")
@pytest.mark.parametrize("launcher", DEFEATS)
def test_each_refused_spelling_really_defeats_the_variable(tmp_path, launcher):
    """Ground the rule in observed behaviour, not in how the flags read."""
    observed = _writes_bytecode(tmp_path, launcher.split())
    if observed is None:
        pytest.skip(f"this env cannot run {launcher!r}")

    assert observed, (
        f"{launcher!r} was refused but leaves the suppression in place, so the "
        "rule refuses a verifier that would have been honest"
    )


@pytest.mark.skipif(POSIX_ENV is None, reason="no POSIX env launcher here")
@pytest.mark.parametrize("launcher", LEAVES_IT_ALONE)
def test_each_accepted_spelling_really_leaves_it_alone(tmp_path, launcher):
    """The other half of the rule: accepting these has to stay safe."""
    observed = _writes_bytecode(tmp_path, launcher.split())
    if observed is None:
        pytest.skip(f"this env cannot run {launcher!r}")

    assert not observed, (
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
    assert _writes_bytecode(tmp_path, [f"{BYTECODE_VARIABLE}=1"]) is False

    python = Path(sys.executable).as_posix()
    with pytest.raises(ValueError, match="drop it"):
        parse_command(f"env {BYTECODE_VARIABLE}=1 {python} -m pytest -q")


@pytest.mark.parametrize(
    "command",
    [
        "env -u PYTHONDONTWRITEBYTECODE pytest -q",
        "env -i pytest -q",
        "env - pytest -q",
        "env PYTHONDONTWRITEBYTECODE= pytest -q",
        "env -i npm test",
    ],
)
def test_a_stripping_launcher_with_no_interpreter_to_vouch_for_it(command):
    """A direct pytest has no interpreter token, so nothing can prove it safe.

    Running one behind `env -u` writes bytecode into the protected tree and
    ends an honest run as TAMPERED, and there is no flag to read that would
    have said otherwise -- so the command is refused rather than trusted.
    """
    with pytest.raises(ValueError, match="no interpreter is named"):
        parse_command(command)


@pytest.mark.parametrize(
    "command",
    ["env pytest -q", "uv run pytest -q", "env -u SOMETHING_ELSE pytest -q"],
)
def test_a_launcher_that_touches_nothing_still_runs_a_bare_pytest(command):
    """The refusal is about stripping the variable, not about the launcher."""
    assert parse_command(command)


@pytest.mark.skipif(POSIX_ENV is None, reason="no POSIX env launcher here")
def test_a_direct_pytest_really_writes_bytecode_when_the_variable_is_gone(tmp_path):
    """The evidence for the refusal above, rather than a reading of the flags."""
    pytest_binary = shutil.which("pytest")
    if pytest_binary is None:
        pytest.skip("no pytest executable on PATH")

    protected = tmp_path / "tests"
    protected.mkdir()
    (protected / "__init__.py").write_text("", encoding="utf-8")
    (protected / "helper_mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    (protected / "test_v.py").write_text(
        "from tests.helper_mod import VALUE\n\n\ndef test_v():\n    assert VALUE == 1\n",
        encoding="utf-8",
    )
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")

    subprocess.run(
        [POSIX_ENV, "-u", BYTECODE_VARIABLE, pytest_binary, "-q"],
        cwd=tmp_path,
        capture_output=True,
        check=False,
        env=_environment_that_forbids_bytecode(),
    )

    assert (protected / "__pycache__").exists(), (
        "expected a direct pytest to write bytecode once the variable is gone"
    )


@pytest.mark.parametrize(
    "command",
    [
        "env -u python {python} -I -m pytest -q",
        "env --unset python {python} -I -m pytest -q",
        "env -upython {python} -I -m pytest -q",
    ],
)
def test_an_operand_named_like_python_does_not_hide_the_interpreter(command):
    """`env -u python` unsets a variable that happens to be named python.

    Reading that operand as the interpreter stops the scan before the real
    one, so every flag it carries -- here an isolated -I with no -B -- goes
    unread and the verifier is accepted.
    """
    python = Path(sys.executable).as_posix()

    with pytest.raises(ValueError, match="isolated Python"):
        parse_command(command.format(python=python))


def test_the_same_operand_still_allows_a_safe_interpreter():
    """The operand is skipped, not the checking: -B still makes it safe."""
    python = Path(sys.executable).as_posix()

    assert parse_command(f"env -u python {python} -I -B -m pytest -q")


@pytest.mark.parametrize(
    "command",
    [
        "env -C python {python} -I -m pytest -q",
        "env --chdir python {python} -I -m pytest -q",
        "env -Cpython {python} -I -m pytest -q",
    ],
)
def test_a_chdir_operand_named_like_python_does_not_hide_the_interpreter(command):
    """-C takes a directory, and a directory may be named python too."""
    python = Path(sys.executable).as_posix()

    with pytest.raises(ValueError, match="isolated Python"):
        parse_command(command.format(python=python))


def test_every_env_option_that_takes_a_value_is_known():
    """The launcher walk has to agree with env about which options consume one.

    An option whose operand is not consumed leaves that operand readable as a
    command, which is how `-u python` and `--chdir pytest` each hid the real
    one. env documents exactly three; the --block-signal family takes an
    optional argument, which a long option can only carry with `=`.
    """
    from theustadlib import verifier

    assert set(verifier._VALUE_LAUNCHER_OPTIONS) == {"u", "C", "S"}


@pytest.mark.parametrize(
    "command",
    [
        "npm test -- -i",
        "true -i",
        "make test -i",
        "cargo test -- --ignored",
        "some-runner -u PYTHONDONTWRITEBYTECODE",
    ],
)
def test_another_program_s_arguments_are_not_env_options(command):
    """These are env's option semantics, so they are read only for env.

    `npm test -- -i` passes -i to npm. Reading it as env's clear-the-
    environment flag refuses a verifier that never touches Python at all.
    """
    assert parse_command(command)


@pytest.mark.parametrize(
    "command",
    ["env -i {python} -m pytest -q", "env -u PYTHONDONTWRITEBYTECODE pytest -q"],
)
def test_env_itself_is_still_read_as_env(command):
    """Narrowing where the rules apply must not narrow the rules."""
    python = Path(sys.executable).as_posix()

    with pytest.raises(ValueError):
        parse_command(command.format(python=python))
