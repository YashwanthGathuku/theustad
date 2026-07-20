#!/usr/bin/env python3
"""Deterministic adapter between Codex plugin skills and Gate v2."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class PluginError(RuntimeError):
    """A user-actionable Gate plugin preflight failure."""


@dataclass(frozen=True)
class DoctorReport:
    repo: Path
    python: Path
    python_version: str
    codex: Path
    codex_version: str
    verifier: str
    state_home: Path


CaptureRunner = Callable[
    [list[str], Path | None],
    subprocess.CompletedProcess[str],
]
Which = Callable[[str], str | None]


def run_capture(
    argv: list[str],
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        shell=False,
        check=False,
    )


def ensure_supported_platform(*, os_name: str | None = None) -> None:
    current = os.name if os_name is None else os_name
    if current == "nt":
        raise PluginError(
            "Gate requires Linux, macOS, or WSL 2; "
            "native Windows process-tree termination is unsupported."
        )


def resolve_repo(repo: Path | None, *, cwd: Path | None = None) -> Path:
    candidate = Path.cwd() if repo is None and cwd is None else (cwd if repo is None else repo)
    if candidate is None:
        raise PluginError("unable to resolve the target directory")
    try:
        candidate = Path(candidate).expanduser().resolve(strict=True)
    except OSError as error:
        raise PluginError(f"target directory does not exist: {candidate}") from error
    if not candidate.is_dir():
        raise PluginError(f"target is not a directory: {candidate}")

    git = shutil.which("git")
    if git is None:
        raise PluginError("git is required to resolve the target repository")
    result = run_capture([git, "-C", str(candidate), "rev-parse", "--show-toplevel"])
    if result.returncode != 0 or not result.stdout.strip():
        detail = result.stderr.strip() or str(candidate)
        raise PluginError(f"target must be a Git repository: {detail}")
    return Path(result.stdout.strip()).resolve(strict=True)


def default_state_home(
    *,
    environ: Mapping[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    values = os.environ if environ is None else environ
    if values.get("GATE_STATE_HOME"):
        root = Path(values["GATE_STATE_HOME"])
    elif values.get("XDG_STATE_HOME"):
        root = Path(values["XDG_STATE_HOME"]) / "gate"
    else:
        user_home = Path.home() if home is None else Path(home)
        root = user_home / ".local" / "state" / "gate"
    return root.expanduser().resolve(strict=False)


def _validate_external_state_home(repo: Path, state_home: Path) -> None:
    if state_home == repo or state_home.is_relative_to(repo):
        raise PluginError("Gate state must remain outside the target repository")


def allocate_state_dir(
    repo: Path,
    *,
    state_home: Path | None = None,
) -> Path:
    target = Path(repo).resolve(strict=True)
    root = (
        default_state_home()
        if state_home is None
        else Path(state_home).expanduser().resolve(strict=False)
    )
    _validate_external_state_home(target, root)

    canonical = os.path.normcase(str(target))
    repo_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{timestamp}-{uuid.uuid4().hex[:8]}"
    destination = root / repo_id / run_id
    destination.mkdir(parents=True, mode=0o700, exist_ok=False)
    try:
        destination.chmod(0o700)
    except OSError:
        pass
    return destination


def _require_success(
    result: subprocess.CompletedProcess[str],
    *,
    label: str,
) -> str:
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        raise PluginError(f"{label} failed: {detail}")
    return result.stdout.strip()


def doctor(
    repo: Path,
    *,
    verifier: str | None = None,
    os_name: str | None = None,
    command_runner: CaptureRunner = run_capture,
    which: Which = shutil.which,
    state_home: Path | None = None,
) -> DoctorReport:
    ensure_supported_platform(os_name=os_name)
    if sys.version_info < (3, 10):
        raise PluginError("Gate requires Python 3.10 or newer")

    target = Path(repo).resolve(strict=True)
    python = Path(sys.executable).resolve(strict=True)
    codex_value = which("codex")
    if codex_value is None:
        raise PluginError("Codex CLI was not found on PATH")
    codex = Path(codex_value)

    codex_version = _require_success(
        command_runner([str(codex), "--version"], None),
        label="codex --version",
    )
    exec_help = _require_success(
        command_runner([str(codex), "exec", "--help"], None),
        label="codex exec --help",
    )
    for flag in ("--json", "--sandbox"):
        if flag not in exec_help:
            raise PluginError(f"installed Codex exec does not expose required {flag} support")
    resume_help = _require_success(
        command_runner([str(codex), "exec", "resume", "--help"], None),
        label="codex exec resume --help",
    )
    if "SESSION_ID" not in resume_help and "THREAD_ID" not in resume_help:
        raise PluginError("installed Codex does not expose exact session-ID resume")
    _require_success(
        command_runner([str(codex), "login", "status"], None),
        label="codex login status",
    )

    verifier_label = verifier or "isolated pytest"
    if verifier is None:
        _require_success(
            command_runner(
                [
                    str(python),
                    "-I",
                    "-c",
                    "import pytest; print(pytest.__version__)",
                ],
                target,
            ),
            label=f"isolated pytest import with {python}",
        )

    resolved_state_home = (
        default_state_home()
        if state_home is None
        else Path(state_home).expanduser().resolve(strict=False)
    )
    _validate_external_state_home(target, resolved_state_home)
    return DoctorReport(
        repo=target,
        python=python,
        python_version=platform.python_version(),
        codex=codex,
        codex_version=codex_version,
        verifier=verifier_label,
        state_home=resolved_state_home,
    )
