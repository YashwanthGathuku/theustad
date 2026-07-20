#!/usr/bin/env python3
"""Deterministic adapter between Codex plugin skills and Gate v2."""

from __future__ import annotations

import argparse
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


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


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
ProcessRunner = Callable[[list[str], Path | None], int]


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


def run_streaming(argv: list[str], cwd: Path | None = None) -> int:
    return subprocess.run(
        argv,
        cwd=cwd,
        shell=False,
        check=False,
    ).returncode


def ensure_supported_platform(*, os_name: str | None = None) -> None:
    current = os.name if os_name is None else os_name
    if current == "nt":
        raise PluginError(
            "Gate requires Linux, macOS, or WSL 2; "
            "native Windows process-tree termination is unsupported."
        )


def current_python() -> Path:
    python = Path(os.path.abspath(sys.executable))
    if not python.is_file():
        raise PluginError(f"current Python executable does not exist: {python}")
    return python


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
    python = current_python()
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


def build_gate_argv(
    *,
    repo: Path,
    task_path: Path,
    state_dir: Path,
    verifier: str | None,
    timeout: float,
    max_retries: int,
) -> list[str]:
    argv = [
        str(current_python()),
        str(PLUGIN_ROOT / "gate.py"),
        "--repo",
        str(repo),
        "--task",
        str(task_path),
        "--state-dir",
        str(state_dir),
        "--log",
        str(state_dir / "logs"),
        "--timeout",
        str(timeout),
        "--max-retries",
        str(max_retries),
        "--no-color",
    ]
    if verifier is not None:
        argv.extend(["--verifier", verifier])
    return argv


def run_gate(
    args: argparse.Namespace,
    process_runner: ProcessRunner = run_streaming,
) -> int:
    repo = resolve_repo(args.repo)
    doctor(
        repo,
        verifier=args.verifier,
        state_home=args.state_home,
    )
    state_dir = allocate_state_dir(repo, state_home=args.state_home)

    if args.task_text is not None:
        task_path = state_dir / "task.txt"
        task_path.write_text(args.task_text, encoding="utf-8")
    else:
        try:
            task_path = Path(args.task_file).expanduser().resolve(strict=True)
        except OSError as error:
            raise PluginError(f"task file does not exist: {args.task_file}") from error
        if not task_path.is_file():
            raise PluginError(f"task file is not a regular file: {task_path}")

    argv = build_gate_argv(
        repo=repo,
        task_path=task_path,
        state_dir=state_dir,
        verifier=args.verifier,
        timeout=args.timeout,
        max_retries=args.max_retries,
    )
    print(f"GATE_PLUGIN_STATE {state_dir}")
    return process_runner(argv, PLUGIN_ROOT)


def build_audit_argv(log_path: Path) -> list[str]:
    return [
        str(current_python()),
        str(PLUGIN_ROOT / "verify_chain.py"),
        str(log_path),
    ]


def run_audit(
    args: argparse.Namespace,
    process_runner: ProcessRunner = run_streaming,
) -> int:
    try:
        log_path = Path(args.log_path).expanduser().resolve(strict=True)
    except OSError as error:
        raise PluginError(f"audit log does not exist: {args.log_path}") from error
    if not log_path.is_file():
        raise PluginError(f"audit log is not a regular file: {log_path}")
    return process_runner(build_audit_argv(log_path), PLUGIN_ROOT)


def _positive(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _nonnegative(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gate-plugin",
        description="Run the bundled Gate v2 runtime from a Codex plugin.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="check Gate prerequisites")
    doctor_parser.add_argument("--repo", type=Path)
    doctor_parser.add_argument("--verifier")
    doctor_parser.add_argument("--state-home", type=Path)

    run_parser = subparsers.add_parser("run", help="run a Gate-controlled Codex task")
    run_parser.add_argument("--repo", type=Path)
    tasks = run_parser.add_mutually_exclusive_group(required=True)
    tasks.add_argument("--task-text")
    tasks.add_argument("--task-file", type=Path)
    run_parser.add_argument("--verifier")
    run_parser.add_argument("--state-home", type=Path)
    run_parser.add_argument("--timeout", type=_positive, default=600.0)
    run_parser.add_argument("--max-retries", type=_nonnegative, default=3)

    audit_parser = subparsers.add_parser("audit", help="verify a Gate audit chain")
    audit_parser.add_argument("log_path", type=Path)
    return parser


def _run_doctor(args: argparse.Namespace) -> int:
    repo = resolve_repo(args.repo)
    report = doctor(
        repo,
        verifier=args.verifier,
        state_home=args.state_home,
    )
    print(f"GATE_DOCTOR_REPO {report.repo}")
    print(f"GATE_DOCTOR_PYTHON {report.python} ({report.python_version})")
    print(f"GATE_DOCTOR_CODEX {report.codex} ({report.codex_version})")
    print(f"GATE_DOCTOR_VERIFIER {report.verifier}")
    print(f"GATE_DOCTOR_STATE_HOME {report.state_home}")
    print("GATE_DOCTOR_OK")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "doctor":
            return _run_doctor(args)
        if args.command == "run":
            return run_gate(args)
        if args.command == "audit":
            return run_audit(args)
        raise PluginError(f"unsupported command: {args.command}")
    except (OSError, PluginError) as error:
        print(f"GATE_PLUGIN_ERROR {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
