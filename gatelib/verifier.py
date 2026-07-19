"""Trusted verifier command parsing and execution."""

import os
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


TAIL_LINES = 30
TIMEOUT_EXIT_CODE = 124
_SHELL_OPERATOR_CHARS = frozenset("|&;<>")


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
    return argv


def _group_exists(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _signal_group(process_group: int, signal_number: int) -> None:
    try:
        os.killpg(process_group, signal_number)
    except ProcessLookupError:
        pass


def _terminate_process_group(
    process: subprocess.Popen[str], *, grace: float = 0.5
) -> None:
    if os.name == "posix":
        _signal_group(process.pid, signal.SIGTERM)
        deadline = time.monotonic() + grace
        while _group_exists(process.pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        if _group_exists(process.pid):
            _signal_group(process.pid, signal.SIGKILL)
    elif process.poll() is None:
        process.terminate()

    if process.poll() is None:
        try:
            process.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                _signal_group(process.pid, signal.SIGKILL)
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
