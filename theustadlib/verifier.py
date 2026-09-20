"""Trusted verifier command parsing and execution."""

import os
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Iterator, Sequence

from .childenv import child_environment


TAIL_LINES = 30
TIMEOUT_EXIT_CODE = 124
_SHELL_OPERATOR_CHARS = frozenset("|&;<>")
# Options whose short-flag cluster consumes a value, ending the cluster.
_VALUE_OPTIONS = frozenset("XWQ")
_PYCACHE_PREFIX = "pycache_prefix="
BYTECODE_VARIABLE = "PYTHONDONTWRITEBYTECODE"
# ``env`` treats a bare ``-`` as ``-i``; its --help documents both.
_ENV_IGNORE = frozenset({"-i", "--ignore-environment", "-"})
_UNSET_LONG = "--unset"
_SPLIT_LONG = "--split-string"
# The only CPython long option that takes a separate value; skipping it
# without its value would end the scan on the value token.
_VALUE_LONG_OPTIONS = frozenset({"--check-hash-based-pycs"})


def _is_python_interpreter(argument: str) -> bool:
    name = PurePath(argument).name.lower()
    if name.endswith(".exe"):
        name = name[: -len(".exe")]
    if name in ("py", "pythonw"):
        return True
    if not name.startswith("python"):
        return False
    suffix = name[len("python") :]
    return suffix == "" or all(character in "0123456789." for character in suffix)


@dataclass(frozen=True)
class InterpreterFlags:
    """What an interpreter's own flags say about where bytecode will land."""

    ignores_environment: bool
    suppresses_writes: bool
    pycache_prefix: str | None


def interpreter_index(argv: Sequence[str]) -> int | None:
    """Find the Python interpreter, looking past a launcher that wraps it.

    ``env python -I ...``, ``uv run python -I ...`` and ``poetry run python
    -I ...`` all hide the interpreter behind another argv[0]; reading only
    argv[0] would skip the check entirely for every one of them.
    """
    for index, token in enumerate(argv):
        if _is_python_interpreter(token):
            return index
    return None


def _launcher_actions(
    argv: Sequence[str], before: int
) -> "Iterator[tuple[str, str]]":
    """Normalise what an ``env``-style launcher does before Python starts.

    ``env`` accepts each option in several spellings -- clustered
    (``-iu NAME``), attached (``-uNAME``), separated (``--unset NAME``) and
    joined (``--unset=NAME``) -- and takes ``NAME=VALUE`` assignments as
    positional arguments.  Reading one spelling of each leaves the rest as
    ways through, so every caller below reads the same normalised view.
    """
    index = 0
    while index < before:
        token = argv[index]
        if token in _ENV_IGNORE:
            yield ("ignore", "")
        elif token == _SPLIT_LONG or token.startswith(f"{_SPLIT_LONG}="):
            yield ("split", "")
        elif token.startswith(f"{_UNSET_LONG}="):
            yield ("unset", token[len(_UNSET_LONG) + 1 :])
        elif token == _UNSET_LONG:
            index += 1
            yield ("unset", argv[index] if index < before else "")
        elif token.startswith("--") or not token.startswith("-"):
            name, separator, _ = token.partition("=")
            if separator:
                yield ("assign", name)
        else:
            for position, letter in enumerate(token[1:]):
                if letter == "i":
                    yield ("ignore", "")
                    continue
                if letter == "S":
                    yield ("split", "")
                    break
                if letter == "u":
                    # -u takes a value: the rest of the cluster, or the
                    # next token, and either way the cluster ends here.
                    value = token[position + 2 :]
                    if not value and index + 1 < before:
                        index += 1
                        value = argv[index]
                    yield ("unset", value)
                    break
        index += 1


def overrides_bytecode_environment(argv: Sequence[str], before: int) -> bool:
    """Report a launcher that stops the variable TheUstad sets from taking.

    ``env -i`` clears the whole environment and ``env -u NAME`` drops one
    variable, both before the interpreter ever starts, so inspecting only
    interpreter flags would miss them and an honest run would be reported as
    TAMPERED.  An assignment does it too: CPython reads ``PYTHONDONTWRITEBYTECODE=``
    as unset and ``=0`` as off, both of which let bytecode into the protected
    tree.  Deciding which *other* values CPython reads as on would mean
    reproducing its integer parsing, so any assignment to the variable is
    refused -- TheUstad already sets it, and the message says to drop it.
    """
    for kind, value in _launcher_actions(argv, before):
        if kind == "ignore":
            return True
        if kind in ("unset", "assign") and value == BYTECODE_VARIABLE:
            return True
    return False


def hides_the_command(argv: Sequence[str]) -> bool:
    """Report a launcher that packs the command into a single argument.

    ``env -S'...'`` re-splits its argument into arguments of its own, so the
    interpreter and its flags are not argv tokens at all and every check here
    looks straight past them -- including the one that finds the interpreter.
    """
    interpreter = interpreter_index(argv)
    limit = len(argv) if interpreter is None else interpreter
    return any(kind == "split" for kind, _ in _launcher_actions(argv, limit))


def scan_interpreter_flags(
    argv: Sequence[str], start: int = 1
) -> InterpreterFlags:
    """Read the interpreter flags that decide whether bytecode is written.

    Scanning stops at ``-m``, ``-c``, ``--`` or the script, so arguments
    belonging to the program under test are never read as interpreter flags.
    """
    ignores_environment = False
    suppresses_writes = False
    pycache_prefix: str | None = None

    index = start
    while index < len(argv):
        token = argv[index]
        if token in ("-m", "-c", "--") or not token.startswith("-"):
            break
        letters = token[1:]
        if letters.startswith("-"):
            index += 2 if token in _VALUE_LONG_OPTIONS else 1
            continue
        consumed_value = False
        for position, letter in enumerate(letters):
            if letter in ("I", "E"):
                ignores_environment = True
            elif letter == "B":
                suppresses_writes = True
            elif letter in _VALUE_OPTIONS:
                value = letters[position + 1 :]
                if not value and index + 1 < len(argv):
                    value = argv[index + 1]
                    consumed_value = True
                if letter == "X" and value.startswith(_PYCACHE_PREFIX):
                    # CPython reads an empty value as no prefix at all
                    # (sys.pycache_prefix is None), so bytecode still lands
                    # beside the source.  Only a real path redirects it.
                    prefix = value[len(_PYCACHE_PREFIX) :]
                    if prefix:
                        pycache_prefix = prefix
                break
        index += 2 if consumed_value else 1

    return InterpreterFlags(
        ignores_environment=ignores_environment,
        suppresses_writes=suppresses_writes,
        pycache_prefix=pycache_prefix,
    )


def ignores_bytecode_environment(argv: Sequence[str]) -> bool:
    """Report a Python verifier that writes bytecode beside the source.

    ``-I`` implies ``-E``, so isolated Python ignores every ``PYTHON*``
    variable including ``PYTHONDONTWRITEBYTECODE``.  ``-B`` and
    ``-X pycache_prefix=PATH`` are command-line options, which isolated mode
    still honours.  Where a prefix *sends* the bytecode is a separate
    question -- see ``bytecode_conflict``.
    """
    index = interpreter_index(argv)
    if index is None:
        return False
    flags = scan_interpreter_flags(argv, index + 1)
    if not (flags.ignores_environment or overrides_bytecode_environment(argv, index)):
        return False
    return not (flags.suppresses_writes or flags.pycache_prefix)


def bytecode_conflict(
    argv: Sequence[str], repo: str | os.PathLike[str] | None = None
) -> str | None:
    """Return why this verifier would falsely report TAMPERED, or ``None``.

    A redirected cache is only safe if it lands outside the repository: the
    prefix is resolved against the verifier's working directory, so a
    repository-relative value such as ``tests/cache`` writes a parallel tree
    straight into the protected paths it was meant to avoid.
    """
    if hides_the_command(argv):
        return (
            "env -S packs the whole command into one argument, so TheUstad "
            "cannot see the interpreter or its flags and cannot tell where "
            "bytecode would land; write the command out as separate arguments"
        )

    index = interpreter_index(argv)
    if index is None:
        # No interpreter token to read, so nothing here can prove the command
        # safe.  A direct pytest executable behind such a launcher does write
        # bytecode into the protected tree -- confirmed by running one -- and
        # an honest run then ends as TAMPERED, so this fails closed.
        if overrides_bytecode_environment(argv, len(argv)):
            return (
                f"this launcher stops the {BYTECODE_VARIABLE} TheUstad sets "
                "from reaching Python, and no interpreter is named here to "
                "show that the command is safe anyway; drop it, or name the "
                "interpreter with -B"
            )
        return None
    flags = scan_interpreter_flags(argv, index + 1)
    if (
        not (flags.ignores_environment or overrides_bytecode_environment(argv, index))
        or flags.suppresses_writes
    ):
        return None

    prefix = flags.pycache_prefix
    if prefix is None:
        if flags.ignores_environment:
            cause = "isolated Python ignores PYTHONDONTWRITEBYTECODE"
        else:
            cause = (
                f"this launcher stops the {BYTECODE_VARIABLE} TheUstad sets "
                "from reaching Python (CPython reads an empty value as unset "
                "and 0 as off, so an assignment counts too)"
            )
        return (
            f"{cause}, so this verifier would write bytecode into the "
            "protected tree and report an honest run as TAMPERED; drop it, or "
            "add -B, or -X pycache_prefix=DIR pointing outside the repository"
        )

    if repo is None:
        if not PurePath(prefix).is_absolute():
            return (
                f"-X pycache_prefix={prefix} is not an absolute path on this "
                "platform, so where it resolves depends on the verifier's "
                "working directory and it may write bytecode into the protected "
                "tree; use an absolute path outside the repository, or -B"
            )
        return None

    repository = Path(repo).resolve(strict=False)
    resolved = Path(prefix)
    if not resolved.is_absolute():
        resolved = repository / resolved
    resolved = resolved.resolve(strict=False)
    if resolved == repository or repository in resolved.parents:
        return (
            f"-X pycache_prefix={prefix} resolves to {resolved}, inside the "
            "repository, so the verifier would write bytecode into paths it is "
            "meant to leave alone and report an honest run as TAMPERED; point it "
            "outside the repository, or use -B"
        )
    return None


@dataclass(frozen=True)
class VerificationResult:
    argv: tuple[str, ...]
    exit_code: int
    output: str
    tail: tuple[str, ...]
    timed_out: bool
    warning: str | None


def default_argv() -> list[str]:
    """Return the trusted isolated-pytest command."""
    return [os.path.abspath(sys.executable), "-I", "-B", "-m", "pytest", "-q"]


def parse_command(
    command: str, repo: str | os.PathLike[str] | None = None
) -> list[str]:
    """Parse a custom verifier without enabling shell syntax."""
    argv = shlex.split(command)
    if not argv:
        raise ValueError("verifier command cannot be empty")
    if any(
        character in argument
        for argument in argv
        for character in _SHELL_OPERATOR_CHARS
    ):
        raise ValueError("shell operators are unsupported in verifier commands")
    conflict = bytecode_conflict(argv, repo)
    if conflict is not None:
        raise ValueError(conflict)
    return argv


def _group_exists(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _signal_group(process: subprocess.Popen[str], signal_number: int) -> None:
    try:
        os.killpg(process.pid, signal_number)
    except ProcessLookupError:
        pass
    except PermissionError:
        # macOS can report EPERM after a completed leader becomes inaccessible.
        if process.poll() is None:
            raise


def _terminate_process_group(
    process: subprocess.Popen[str], *, grace: float = 0.5
) -> None:
    if os.name == "posix":
        _signal_group(process, signal.SIGTERM)
        deadline = time.monotonic() + grace
        while _group_exists(process.pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        if _group_exists(process.pid):
            _signal_group(process, signal.SIGKILL)
    elif process.poll() is None:
        process.terminate()

    if process.poll() is None:
        try:
            process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                _signal_group(process, signal.SIGKILL)
            else:
                process.kill()
            process.wait(timeout=grace)


def run(
    argv: Sequence[str] | None,
    repo: str | os.PathLike[str],
    timeout: float = 120,
) -> VerificationResult:
    """Run a verifier as trusted argv and capture merged evidence."""
    command = list(default_argv() if argv is None else argv)
    if not command:
        raise ValueError("verifier argv cannot be empty")
    if timeout <= 0:
        raise ValueError("verifier timeout must be positive")

    process = subprocess.Popen(
        command,
        cwd=Path(repo),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        start_new_session=os.name == "posix",
        env=child_environment(),
    )

    timed_out = False
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process_group(process)
        output, _ = process.communicate()
    else:
        _terminate_process_group(process)

    output = output or ""
    if timed_out:
        warning = f"VERIFIER_TIMEOUT after {timeout:g} seconds"
        output = output.rstrip("\r\n")
        output = f"{output}\n{warning}" if output else warning
        exit_code = TIMEOUT_EXIT_CODE
    else:
        warning = None if output.strip() else "Verifier produced no output."
        exit_code = process.returncode

    return VerificationResult(
        argv=tuple(command),
        exit_code=exit_code,
        output=output,
        tail=tuple(output.splitlines()[-TAIL_LINES:]),
        timed_out=timed_out,
        warning=warning,
    )
