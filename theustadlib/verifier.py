"""Trusted verifier command parsing and execution."""

import os
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Sequence

from .childenv import child_environment


TAIL_LINES = 30
TIMEOUT_EXIT_CODE = 124
_SHELL_OPERATOR_CHARS = frozenset("|&;<>")
# Options whose short-flag cluster consumes a value, ending the cluster.
_VALUE_OPTIONS = frozenset("XWQ")
_PYCACHE_PREFIX = "pycache_prefix="


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


def ignores_bytecode_environment(argv: Sequence[str]) -> bool:
    """Report a Python verifier that cannot be told to skip bytecode.

    ``-I`` implies ``-E``, so isolated Python ignores every ``PYTHON*``
    variable including ``PYTHONDONTWRITEBYTECODE``.  Such a verifier writes
    ``__pycache__`` into the protected tree and the post-verifier check then
    reports an honest run as TAMPERED.  ``-B`` and ``-X pycache_prefix=`` are
    command-line options, which isolated mode still honours.
    """
    if not argv or not _is_python_interpreter(argv[0]):
        return False

    ignores_environment = False
    suppresses_bytecode = False
    index = 1
    while index < len(argv):
        token = argv[index]
        if token in ("-m", "-c", "--") or not token.startswith("-"):
            break
        letters = token[1:]
        if letters.startswith("-"):
            index += 1
            continue
        consumed_value = False
        for position, letter in enumerate(letters):
            if letter in ("I", "E"):
                ignores_environment = True
            elif letter == "B":
                suppresses_bytecode = True
            elif letter in _VALUE_OPTIONS:
                value = letters[position + 1 :]
                if not value and index + 1 < len(argv):
                    value = argv[index + 1]
                    consumed_value = True
                if letter == "X" and value.startswith(_PYCACHE_PREFIX):
                    # CPython reads an empty value as no prefix at all
                    # (sys.pycache_prefix is None), so bytecode still lands
                    # beside the source.  Only a real path redirects it.
                    if value[len(_PYCACHE_PREFIX) :]:
                        suppresses_bytecode = True
                break
        index += 2 if consumed_value else 1
    return ignores_environment and not suppresses_bytecode


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


def parse_command(command: str) -> list[str]:
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
    if ignores_bytecode_environment(argv):
        raise ValueError(
            "isolated Python ignores PYTHONDONTWRITEBYTECODE, so this verifier "
            "would write bytecode into the protected tree and report an honest "
            "run as TAMPERED; add -B, or -X pycache_prefix=DIR pointing outside "
            "the repository"
        )
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
