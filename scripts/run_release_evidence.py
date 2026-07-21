#!/usr/bin/env python3
"""Generate fail-closed TheUstad A1-A5/B1-B4 release evidence."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
THEUSTAD = ROOT / "theustad.py"
FAKE_CODEX = ROOT / "fake_codex.py"
VERIFY_CHAIN = ROOT / "verify_chain.py"
TASK = ROOT / "task.md"
PYTHON_SEED = ROOT / "tests" / "fixtures" / "demo_repo_seed"
JS_SEED = ROOT / "tests" / "fixtures" / "js_repo_seed"
LEGACY_EVIDENCE = (
    ROOT / "docs" / "evidence" / "real_project_demo",
    ROOT / "docs" / "evidence" / "real_project_video",
)
VERDICTS = frozenset(
    {
        "VERIFIED",
        "FALSIFIED",
        "PASS_NO_CLAIM",
        "INCOMPLETE",
        "TAMPERED",
        "AGENT_ERROR",
        "AGENT_TIMEOUT",
    }
)


@dataclass(frozen=True)
class ParsedOutput:
    verdicts: tuple[str, ...]
    final: str
    audit_log: Path
    root: str


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    exit_code: int
    verdicts: tuple[str, ...]
    state_ok: bool
    audit_ok: bool
    detail: str

    @property
    def passed(self) -> bool:
        return self.state_ok and self.audit_ok and not self.detail


@dataclass(frozen=True)
class AuditCheck:
    copied_path: Path
    valid: bool
    root: str
    detail: str


@dataclass
class EvidenceRun:
    result: ScenarioResult
    command: tuple[str, ...]
    final: str
    transcript: Path
    copied_audit: Path | None
    root: str
    state_label: str


def validate_output_dir(path: Path) -> Path:
    resolved = Path(path).resolve(strict=False)
    for legacy in LEGACY_EVIDENCE:
        old = legacy.resolve(strict=False)
        if resolved == old or resolved.is_relative_to(old):
            raise ValueError(f"refusing legacy evidence output path: {resolved}")
    return resolved


def run_command(
    argv: Sequence[str], cwd: Path, transcript: Path
) -> subprocess.CompletedProcess[str]:
    if not argv or isinstance(argv, (str, bytes)) or not all(
        isinstance(value, str) and value for value in argv
    ):
        raise ValueError("argv must be a non-empty sequence of strings")
    command = list(argv)
    transcript = Path(transcript)
    transcript.parent.mkdir(parents=True, exist_ok=True)
    try:
        completed = subprocess.run(
            command,
            cwd=Path(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
            check=False,
            shell=False,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        output += "[timeout after 180 seconds]\n"
        completed = subprocess.CompletedProcess(command, 124, output)
    with transcript.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(shlex.join(command) + "\n")
        stream.write(completed.stdout or "")
        if completed.stdout and not completed.stdout.endswith("\n"):
            stream.write("\n")
        stream.write(f"[exit {completed.returncode}]\n")
    return completed


def extract_records(output: str) -> ParsedOutput:
    rounds = re.findall(r"^ROUND (\d+) (\S+)$", output, flags=re.MULTILINE)
    finals = re.findall(r"^FINAL (\S+)$", output, flags=re.MULTILINE)
    audits = re.findall(r"^AUDIT_LOG (.+)$", output, flags=re.MULTILINE)
    roots = re.findall(r"^AUDIT_ROOT (\S+)$", output, flags=re.MULTILINE)
    if not rounds:
        raise ValueError("missing ROUND records")
    if [int(number) for number, _ in rounds] != list(range(1, len(rounds) + 1)):
        raise ValueError("ROUND records are not sequential")
    if len(finals) != 1:
        raise ValueError("expected exactly one FINAL record")
    if len(audits) != 1:
        raise ValueError("expected exactly one AUDIT_LOG record")
    if len(roots) != 1 or re.fullmatch(r"[0-9a-f]{64}", roots[0]) is None:
        raise ValueError("expected exactly one valid AUDIT_ROOT record")
    verdicts = tuple(verdict for _, verdict in rounds)
    if any(verdict not in VERDICTS for verdict in (*verdicts, finals[0])):
        raise ValueError("unknown verdict")
    if finals[0] != verdicts[-1]:
        raise ValueError("FINAL does not match the last ROUND")
    return ParsedOutput(verdicts, finals[0], Path(audits[0].strip()), roots[0])


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
    else:
        for child in sorted(path.rglob("*")):
            if child.is_file():
                digest.update(child.relative_to(path).as_posix().encode("utf-8"))
                digest.update(child.read_bytes())
    return digest.hexdigest()


def copy_and_verify_audit(
    source: Path, destination: Path, transcript: Path, expected_root: str
) -> AuditCheck:
    source = Path(source).resolve(strict=True)
    before = source.read_bytes()
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    copied_ok = destination.read_bytes() == before and source.read_bytes() == before
    verified = run_command(
        [sys.executable, str(VERIFY_CHAIN), str(destination)], ROOT, transcript
    )
    match = re.fullmatch(
        r"VALID: \d+ records, root ([0-9a-f]{64})\n?", verified.stdout or ""
    )
    root = match.group(1) if match else ""
    valid = copied_ok and verified.returncode == 0 and root == expected_root
    detail = "" if valid else "copied audit failed independent validation"
    return AuditCheck(destination, valid, root, detail)


def _child_command(scenario: str, *, resume: bool = False) -> str:
    values = [Path(sys.executable).as_posix(), FAKE_CODEX.as_posix(), scenario]
    if resume:
        values += ["--resume", "{thread_id}"]
    return shlex.join(values)


def _theustad_command(
    repo: Path,
    task: Path,
    scenario: str,
    state_dir: Path,
    log_dir: Path,
    max_retries: int,
    extra: Sequence[str] = (),
) -> list[str]:
    return [
        sys.executable,
        str(THEUSTAD),
        "--repo",
        str(repo),
        "--task",
        str(task),
        "--cmd",
        _child_command(scenario),
        "--resume-cmd",
        _child_command(scenario, resume=True),
        *extra,
        "--state-dir",
        str(state_dir),
        "--log",
        str(log_dir),
        "--max-retries",
        str(max_retries),
        "--timeout",
        "30",
        "--no-color",
    ]


def _failure(
    scenario_id: str, transcript: Path, detail: str, command: Sequence[str] = ()
) -> EvidenceRun:
    return EvidenceRun(
        ScenarioResult(scenario_id, 125, (), False, False, detail),
        tuple(command),
        "",
        transcript,
        None,
        "",
        "",
    )


def _execute(
    scenario_id: str,
    command: Sequence[str],
    transcript: Path,
    output: Path,
    expected_verdicts: tuple[str, ...],
    expect_zero: bool,
    state_check: Callable[[], bool],
    state_label: str,
) -> EvidenceRun:
    completed = run_command(command, ROOT, transcript)
    errors: list[str] = []
    parsed: ParsedOutput | None = None
    try:
        parsed = extract_records(completed.stdout or "")
    except (OSError, ValueError) as error:
        errors.append(str(error))
    exit_ok = completed.returncode == 0 if expect_zero else completed.returncode != 0
    if not exit_ok:
        errors.append("unexpected process exit code")
    if parsed is None or parsed.verdicts != expected_verdicts:
        errors.append("unexpected verdict sequence")
    try:
        property_ok = state_check()
    except OSError as error:
        property_ok = False
        errors.append(f"state check failed: {error}")
    if not property_ok:
        errors.append("required state property failed")
    audit: AuditCheck | None = None
    if parsed is not None:
        try:
            audit = copy_and_verify_audit(
                parsed.audit_log,
                output / f"{scenario_id.lower()}-audit.jsonl",
                transcript,
                parsed.root,
            )
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            errors.append(f"audit copy failed: {error}")
    audit_ok = audit is not None and audit.valid
    if not audit_ok:
        errors.append(audit.detail if audit else "audit unavailable")
    detail = "; ".join(dict.fromkeys(errors))
    result = ScenarioResult(
        scenario_id,
        completed.returncode,
        parsed.verdicts if parsed else (),
        exit_ok and parsed is not None and parsed.final == expected_verdicts[-1] and property_ok,
        audit_ok,
        detail,
    )
    return EvidenceRun(
        result,
        tuple(command),
        parsed.final if parsed else "",
        transcript,
        audit.copied_path if audit else None,
        parsed.root if parsed else "",
        state_label,
    )


def _reset_python(repo: Path, transcript: Path) -> subprocess.CompletedProcess[str]:
    return run_command(
        [sys.executable, str(FAKE_CODEX), "reset", "--repo", str(repo)],
        ROOT,
        transcript,
    )


def _python_run(
    work: Path,
    output: Path,
    scenario_id: str,
    scenario: str,
    verdicts: tuple[str, ...],
    expect_zero: bool,
    max_retries: int,
    restored: str | None = None,
) -> EvidenceRun:
    transcript = output / f"{scenario_id.lower()}.txt"
    repo = work / "python-repo"
    reset = _reset_python(repo, transcript)
    if reset.returncode != 0:
        return _failure(scenario_id, transcript, "fixture reset failed")
    target = repo / restored if restored else None
    before = target.read_bytes() if target and target.exists() else None
    command = _theustad_command(
        repo,
        TASK,
        scenario,
        work / "state" / scenario_id,
        work / "logs" / scenario_id,
        max_retries,
    )

    def state_check() -> bool:
        if target is None:
            return True
        return target.read_bytes() == before if before is not None else not target.exists()

    label = f"restored={restored}" if restored else (
        "round=1" if scenario_id == "B2" else "exit=" + ("zero" if expect_zero else "nonzero")
    )
    return _execute(
        scenario_id,
        command,
        transcript,
        output,
        verdicts,
        expect_zero,
        state_check,
        label,
    )


def _b1_run(work: Path, output: Path) -> EvidenceRun:
    scenario_id = "B1"
    transcript = output / "b1.txt"
    npm_value = shutil.which("npm")
    if npm_value is None:
        return _failure(scenario_id, transcript, "absolute npm executable unavailable")
    npm = Path(npm_value).resolve()
    repo = work / "js-repo"
    shutil.copytree(JS_SEED, repo)
    protected = {
        name: _sha256(repo / name)
        for name in ("tests", "package.json", "package-lock.json")
    }
    command = _theustad_command(
        repo,
        repo / "task.md",
        "js_honest",
        work / "state" / scenario_id,
        work / "logs" / scenario_id,
        0,
        (
            "--verifier",
            shlex.join([npm.as_posix(), "test"]),
            "--protect-add",
            "package.json",
            "package-lock.json",
        ),
    )
    return _execute(
        scenario_id,
        command,
        transcript,
        output,
        ("VERIFIED",),
        True,
        lambda: protected
        == {name: _sha256(repo / name) for name in protected},
        "protected=unchanged",
    )


def _b4_run(output: Path, source_run: EvidenceRun) -> EvidenceRun:
    scenario_id = "B4"
    transcript = output / "b4.txt"
    if source_run.copied_audit is None or not source_run.root:
        return _failure(scenario_id, transcript, "no B3 audit available")
    source = source_run.copied_audit
    source_bytes = source.read_bytes()
    tampered = output / "b4-tampered-copy.jsonl"
    shutil.copy2(source, tampered)
    lines = tampered.read_text(encoding="utf-8").splitlines()
    errors: list[str] = []
    only_data = False
    if len(lines) < 2:
        errors.append("B3 audit has no record 1")
    else:
        original_record = json.loads(lines[1])
        changed_record = dict(original_record)
        data = changed_record.get("data")
        changed_record["data"] = (
            {**data, "release_evidence_tamper": True}
            if isinstance(data, dict)
            else {"original": data, "release_evidence_tamper": True}
        )
        only_data = all(
            changed_record[key] == value
            for key, value in original_record.items()
            if key != "data"
        )
        lines[1] = json.dumps(changed_record, sort_keys=True, separators=(",", ":"))
        tampered.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    tamper_command = [sys.executable, str(VERIFY_CHAIN), str(tampered)]
    broken = run_command(tamper_command, ROOT, transcript)
    original = run_command(
        [sys.executable, str(VERIFY_CHAIN), str(source)], ROOT, transcript
    )
    root_match = re.fullmatch(
        r"VALID: \d+ records, root " + re.escape(source_run.root) + r"\n?",
        original.stdout or "",
    ) is not None
    copy_only = source.read_bytes() == source_bytes
    state_ok = (
        only_data
        and copy_only
        and broken.returncode != 0
        and (broken.stdout or "").startswith("BROKEN")
    )
    audit_ok = original.returncode == 0 and root_match
    if not state_ok:
        errors.append("tampered copy was not independently BROKEN")
    if not audit_ok:
        errors.append("original B3 audit was not independently VALID at printed root")
    detail = "; ".join(errors)
    return EvidenceRun(
        ScenarioResult(scenario_id, broken.returncode, (), state_ok, audit_ok, detail),
        tuple(tamper_command),
        "",
        transcript,
        tampered,
        source_run.root,
        "copy=BROKEN original=VALID",
    )


def _summary_line(run: EvidenceRun) -> str:
    result = run.result
    status = "PASS" if result.passed else "FAIL"
    verdict_text = (
        f"verdict={result.verdicts[0]}"
        if len(result.verdicts) == 1
        else "verdicts=" + ",".join(result.verdicts)
    )
    fields = [result.scenario_id, status]
    if result.scenario_id != "B4":
        fields.append(verdict_text)
    if run.state_label:
        fields.append(run.state_label)
    fields.append("audit=VALID" if result.audit_ok else "audit=INVALID")
    fields.append(f"root={run.root or 'MISSING'}")
    if result.detail:
        fields.append("detail=" + result.detail.replace("\n", " "))
    return " ".join(fields)


def _write_summaries(output: Path, runs: Sequence[EvidenceRun]) -> None:
    environment = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "repository": str(ROOT),
    }
    payload = {
        "environment": environment,
        "passed": bool(runs) and all(run.result.passed for run in runs),
        "runs": [
            {
                "scenario_id": run.result.scenario_id,
                "passed": run.result.passed,
                "command": list(run.command),
                "verdicts": list(run.result.verdicts),
                "final": run.final,
                "exit_code": run.result.exit_code,
                "state_check": run.result.state_ok,
                "audit_check": run.result.audit_ok,
                "detail": run.result.detail,
                "transcript_path": str(run.transcript),
                "copied_audit_path": str(run.copied_audit) if run.copied_audit else None,
                "root": run.root,
            }
            for run in runs
        ],
    }
    (output / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "summary.txt").write_text(
        "\n".join(_summary_line(run) for run in runs) + "\n", encoding="utf-8"
    )


def _write_hashes(output: Path) -> None:
    checksum = output / "sha256sums.txt"
    files = sorted(path for path in output.rglob("*") if path.is_file() and path != checksum)
    checksum.write_text(
        "".join(
            f"{_sha256(path)}  {path.relative_to(output).as_posix()}\n" for path in files
        ),
        encoding="utf-8",
    )


def run_matrix(output_dir: Path) -> int:
    output = validate_output_dir(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    runs: list[EvidenceRun] = []
    try:
        with tempfile.TemporaryDirectory(prefix="theustad-release-") as temporary:
            work = Path(temporary)
            specifications = (
                ("A1", "assertion_gut", ("TAMPERED",), False, 0, "tests/test_invoice.py"),
                ("A2", "conftest_poison", ("TAMPERED",), False, 0, "conftest.py"),
                ("A3", "no_claim", ("PASS_NO_CLAIM",), False, 0, None),
                ("A4", "crash", ("AGENT_ERROR",), False, 0, None),
                ("A5", "config_poison", ("TAMPERED",), False, 0, "pytest.ini"),
            )
            for values in specifications:
                try:
                    runs.append(_python_run(work, output, *values))
                except Exception as error:  # summaries must survive unexpected failures
                    runs.append(_failure(values[0], output / f"{values[0].lower()}.txt", str(error)))
            try:
                runs.append(_b1_run(work, output))
            except Exception as error:
                runs.append(_failure("B1", output / "b1.txt", str(error)))
            try:
                runs.append(
                    _python_run(work, output, "B2", "honest", ("VERIFIED",), True, 0)
                )
            except Exception as error:
                runs.append(_failure("B2", output / "b2.txt", str(error)))
            b3_runs: list[EvidenceRun] = []
            for number in range(1, 11):
                scenario_id = f"B3-{number}"
                try:
                    run = _python_run(
                        work,
                        output,
                        scenario_id,
                        "demo3",
                        ("FALSIFIED", "TAMPERED", "VERIFIED"),
                        True,
                        3,
                    )
                except Exception as error:
                    run = _failure(scenario_id, output / f"b3-{number}.txt", str(error))
                b3_runs.append(run)
                runs.append(run)
            sequences = [run.result.verdicts for run in b3_runs]
            identical = len(sequences) == 10 and len(set(sequences)) == 1
            if not identical:
                for run in b3_runs:
                    run.result = dataclasses.replace(
                        run.result,
                        state_ok=False,
                        detail=(run.result.detail + "; " if run.result.detail else "")
                        + "B3 verdict sequences were not identical",
                    )
            try:
                runs.append(_b4_run(output, b3_runs[0]))
            except Exception as error:
                runs.append(_failure("B4", output / "b4.txt", str(error)))
    except Exception as error:
        runs.append(_failure("INTERNAL", output / "internal.txt", str(error)))
    finally:
        _write_summaries(output, runs)
        _write_hashes(output)
    return 0 if len(runs) == 18 and all(run.result.passed for run in runs) else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        exit_code = run_matrix(args.output)
    except (OSError, ValueError) as error:
        print(f"EVIDENCE_ERROR {error}", file=sys.stderr)
        return 2
    print((validate_output_dir(args.output) / "summary.txt").read_text(), end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
