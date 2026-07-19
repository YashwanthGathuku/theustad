#!/usr/bin/env python3
"""Gate v2 command-line orchestrator."""

import argparse
import os
import shlex
import sys
import tempfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TextIO

from gatelib.chain import AuditChain
from gatelib.claims import Claim, find_claims
from gatelib.freezer import (
    DEFAULT_PATTERNS,
    Manifest,
    Tampering,
    check,
    freeze,
    restore,
)
from gatelib.session import (
    DEFAULT_INITIAL_CMD,
    DEFAULT_RESUME_TEMPLATE,
    AgentSession,
    SessionResult,
)
from gatelib.verifier import (
    VerificationResult,
    default_argv,
    parse_command as parse_verifier_command,
    run as run_verifier,
)


class Verdict(str, Enum):
    VERIFIED = "VERIFIED"
    FALSIFIED = "FALSIFIED"
    PASS_NO_CLAIM = "PASS_NO_CLAIM"
    INCOMPLETE = "INCOMPLETE"
    TAMPERED = "TAMPERED"
    AGENT_ERROR = "AGENT_ERROR"
    AGENT_TIMEOUT = "AGENT_TIMEOUT"


@dataclass(frozen=True)
class RoundResult:
    round_number: int
    verdict: Verdict
    agent: SessionResult
    claims: tuple[Claim, ...]
    verification: VerificationResult | None
    tampering: Tampering | None


@dataclass(frozen=True)
class GateResult:
    verdict: Verdict
    exit_code: int
    rounds: tuple[RoundResult, ...]
    log_path: Path
    root: str


ClaimFinder = Callable[[str], list[Claim]]
VerifierRunner = Callable[[Sequence[str], Path, float], VerificationResult]
Output = Callable[[str], None]


def _console_output(line: str, *, stream: TextIO | None = None) -> None:
    target = sys.stdout if stream is None else stream
    encoding = getattr(target, "encoding", None) or "utf-8"
    safe_line = line.encode(encoding, errors="backslashreplace").decode(encoding)
    print(safe_line, file=target)


def verdict_for(claims: Sequence[Claim], verifier_exit_code: int) -> Verdict:
    """Apply the claim/verifier verdict matrix."""
    if claims:
        return Verdict.VERIFIED if verifier_exit_code == 0 else Verdict.FALSIFIED
    return (
        Verdict.PASS_NO_CLAIM
        if verifier_exit_code == 0
        else Verdict.INCOMPLETE
    )


def _tamper_data(stage: str, tampering: Tampering) -> dict[str, Any]:
    return {
        "stage": stage,
        "modified": tampering.modified,
        "deleted": tampering.deleted,
        "added": tampering.added,
    }


def _claim_data(message: str, claims: Sequence[Claim]) -> dict[str, Any]:
    return {
        "message": message,
        "matches": [
            {
                "sentence": claim.sentence,
                "phrases": list(claim.phrases),
            }
            for claim in claims
        ],
    }


def _tamper_resume_message(tampering: Tampering) -> str:
    return (
        "Gate detected protected-input tampering and restored the baseline. "
        "You must fix code rather than trusted tests. "
        f"Modified: {tampering.modified or ['none']}; "
        f"deleted: {tampering.deleted or ['none']}; "
        f"added: {tampering.added or ['none']}. "
        "Continue the task and report an explicit completion status."
    )


def _evidence_resume_message(
    verdict: Verdict, verification: VerificationResult
) -> str:
    evidence = "\n".join(verification.tail) or "Verifier produced no output."
    if verdict is Verdict.FALSIFIED:
        prefix = "Gate falsified the completion claim with the trusted verifier."
    else:
        prefix = "The trusted verifier still fails and the task is incomplete."
    return f"{prefix}\n\nVerifier evidence:\n{evidence}\n\nFix the code and report status."


STATUS_REQUEST = (
    "The trusted verifier passed, but your final message made no explicit "
    "completion claim. Reply once with an explicit completion status."
)


class GateRunner:
    """Execute Gate's ordered verification-and-retry loop."""

    def __init__(
        self,
        *,
        repo: str | os.PathLike[str],
        task: str,
        session: AgentSession,
        verifier_argv: Sequence[str],
        patterns: Iterable[str],
        state_dir: str | os.PathLike[str],
        log_dir: str | os.PathLike[str],
        max_retries: int,
        timeout: float,
        verifier_runner: VerifierRunner = run_verifier,
        claim_finder: ClaimFinder = find_claims,
        output: Output = _console_output,
    ):
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self.repo = Path(repo).resolve(strict=True)
        if not self.repo.is_dir():
            raise ValueError(f"repository is not a directory: {self.repo}")
        self.task = task
        self.session = session
        self.verifier_argv = tuple(verifier_argv)
        self.patterns = tuple(patterns)
        self.state_dir = Path(state_dir)
        self.log_dir = Path(log_dir)
        self.max_retries = max_retries
        self.timeout = timeout
        self.verifier_runner = verifier_runner
        self.claim_finder = claim_finder
        self.output = output

    def _record_session(
        self,
        audit: AuditChain,
        round_number: int,
        result: SessionResult,
    ) -> None:
        audit.append(
            round_number=round_number,
            kind="session",
            data={
                "argv": list(result.argv),
                "thread_id": result.thread_id,
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
                "last_agent_message": result.last_agent_message,
                "non_json_tail": list(result.non_json_tail),
            },
        )
        for warning in result.warnings:
            audit.append(
                round_number=round_number,
                kind="warning",
                data={"message": warning},
            )

    def _restore_tampering(
        self,
        audit: AuditChain,
        manifest: Manifest,
        round_number: int,
        stage: str,
        tampering: Tampering,
    ) -> None:
        audit.append(
            round_number=round_number,
            kind="tamper",
            data=_tamper_data(stage, tampering),
        )
        restore(self.repo, manifest)

    def _record_verdict(
        self,
        audit: AuditChain,
        result: RoundResult,
    ) -> None:
        verification = result.verification
        audit.append(
            round_number=result.round_number,
            kind="verdict",
            data={
                "verdict": result.verdict.value,
                "claims": len(result.claims),
                "agent_exit_code": result.agent.exit_code,
                "verifier_exit_code": (
                    verification.exit_code if verification is not None else None
                ),
                "tampering": (
                    _tamper_data("detected", result.tampering)
                    if result.tampering is not None
                    else None
                ),
            },
        )
        self.output(f"ROUND {result.round_number} {result.verdict.value}")

    def run(self) -> GateResult:
        manifest = freeze(self.repo, self.patterns, self.state_dir)
        audit = AuditChain(self.log_dir)
        rounds: list[RoundResult] = []
        resume_message: str | None = None
        status_resume_used = False

        for round_number in range(1, self.max_retries + 2):
            if resume_message is None:
                agent_result = self.session.start(self.task, on_line=self.output)
            else:
                audit.append(
                    round_number=round_number,
                    kind="resume",
                    data={"message": resume_message},
                )
                agent_result = self.session.resume(
                    resume_message,
                    on_line=self.output,
                )
                resume_message = None

            claims: tuple[Claim, ...] = ()
            verification: VerificationResult | None = None
            tampering: Tampering | None = None

            tampering = check(self.repo, manifest)
            self._record_session(audit, round_number, agent_result)
            if tampering:
                self._restore_tampering(
                    audit,
                    manifest,
                    round_number,
                    "post_agent",
                    tampering,
                )
                verdict = Verdict.TAMPERED
            elif agent_result.timed_out:
                verdict = Verdict.AGENT_TIMEOUT
            elif agent_result.exit_code != 0:
                verdict = Verdict.AGENT_ERROR
            else:
                message = agent_result.last_agent_message or ""
                claims = tuple(self.claim_finder(message))
                audit.append(
                    round_number=round_number,
                    kind="claim",
                    data=_claim_data(message, claims),
                )

                tampering = check(self.repo, manifest)
                if tampering:
                    self._restore_tampering(
                        audit,
                        manifest,
                        round_number,
                        "pre_verifier",
                        tampering,
                    )
                    verdict = Verdict.TAMPERED
                else:
                    verification = self.verifier_runner(
                        self.verifier_argv,
                        self.repo,
                        self.timeout,
                    )
                    tampering = check(self.repo, manifest)
                    if tampering:
                        self._restore_tampering(
                            audit,
                            manifest,
                            round_number,
                            "post_verifier",
                            tampering,
                        )
                        verdict = Verdict.TAMPERED
                    else:
                        verdict = verdict_for(claims, verification.exit_code)
                    if verification.warning:
                        audit.append(
                            round_number=round_number,
                            kind="warning",
                            data={"message": verification.warning},
                        )

            round_result = RoundResult(
                round_number=round_number,
                verdict=verdict,
                agent=agent_result,
                claims=claims,
                verification=verification,
                tampering=tampering if tampering else None,
            )
            rounds.append(round_result)
            self._record_verdict(audit, round_result)

            retries_remain = round_number <= self.max_retries
            if verdict is Verdict.VERIFIED:
                break
            if verdict in (Verdict.AGENT_ERROR, Verdict.AGENT_TIMEOUT):
                break
            if verdict is Verdict.PASS_NO_CLAIM:
                if status_resume_used or not retries_remain:
                    break
                status_resume_used = True
                resume_message = STATUS_REQUEST
                continue
            if not retries_remain:
                break
            if verdict is Verdict.TAMPERED:
                if round_result.tampering is None:
                    raise RuntimeError("TAMPERED verdict is missing file evidence")
                resume_message = _tamper_resume_message(round_result.tampering)
            elif verification is not None:
                resume_message = _evidence_resume_message(verdict, verification)
            else:
                break

        final_verdict = rounds[-1].verdict
        exit_code = 0 if final_verdict is Verdict.VERIFIED else 1
        audit.append(
            round_number=rounds[-1].round_number,
            kind="final",
            data={"verdict": final_verdict.value, "exit_code": exit_code},
        )
        self.output(f"FINAL {final_verdict.value}")
        self.output(f"AUDIT_LOG {audit.path}")
        self.output(f"AUDIT_ROOT {audit.root}")
        self.output(
            "Anchor this SHA-256 root in a pushed Git commit and submission text."
        )
        return GateResult(
            verdict=final_verdict,
            exit_code=exit_code,
            rounds=tuple(rounds),
            log_path=audit.path,
            root=audit.root,
        )


def _nonnegative(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return parsed


def _positive(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return parsed


def _command_argv(command: str, label: str) -> list[str]:
    argv = shlex.split(command)
    if not argv:
        raise ValueError(f"{label} cannot be empty")
    if any(character in argument for argument in argv for character in "|&;<>"):
        raise ValueError(f"{label} cannot contain shell operators")
    return argv


def _task_text(value: str | None) -> str:
    if value is None:
        return "Complete the repository task and report an explicit status."
    candidate = Path(value)
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gate.py",
        description="Verify coding-agent completion claims with protected evidence.",
    )
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--task", help="task text or path to a task file")
    parser.add_argument("--cmd", help="custom initial agent command")
    parser.add_argument("--resume-cmd", help="custom resume command template")
    parser.add_argument("--verifier", help="custom verifier command without shell syntax")
    parser.add_argument(
        "--protect",
        action="append",
        nargs="+",
        metavar="PATTERN",
        help="protected path pattern; may be repeated",
    )
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--max-retries", type=_nonnegative, default=3)
    parser.add_argument("--timeout", type=_positive, default=600.0)
    parser.add_argument("--log", type=Path, help="directory for timestamped audit logs")
    parser.add_argument("--no-color", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        repo = args.repo.resolve(strict=True)
        task = _task_text(args.task)
        initial_cmd = (
            _command_argv(args.cmd, "agent command")
            if args.cmd
            else list(DEFAULT_INITIAL_CMD)
        )
        resume_template = (
            _command_argv(args.resume_cmd, "resume command")
            if args.resume_cmd
            else list(DEFAULT_RESUME_TEMPLATE)
        )
        verifier_argv = (
            parse_verifier_command(args.verifier)
            if args.verifier
            else default_argv()
        )
        patterns = (
            tuple(pattern for group in args.protect for pattern in group)
            if args.protect
            else DEFAULT_PATTERNS
        )
        state_dir = args.state_dir or Path(
            tempfile.mkdtemp(prefix="gate-v2-state-")
        )
        log_dir = args.log or state_dir / "logs"
        session = AgentSession(
            initial_cmd,
            resume_template,
            repo,
            args.timeout,
        )
        runner = GateRunner(
            repo=repo,
            task=task,
            session=session,
            verifier_argv=verifier_argv,
            patterns=patterns,
            state_dir=state_dir,
            log_dir=log_dir,
            max_retries=args.max_retries,
            timeout=args.timeout,
        )
        return runner.run().exit_code
    except (OSError, ValueError, RuntimeError) as error:
        _console_output(f"GATE_ERROR {error}", stream=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
