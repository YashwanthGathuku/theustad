"""Check a finished change against the acceptance tests it started from.

The wrapper and hook mode supervise an agent while it works. CI mode needs no
agent integration at all: whatever produced the change -- Codex, Claude Code,
opencode, a script, a person -- it arrives as commits, and the question is the
one a careful reviewer asks. Do the acceptance tests the change started from
still pass, unedited, on the new code?

The answer is computed from three things the change cannot edit:

* the protected inputs, read from git objects of the commit the change started
  from (the merge base), never from the checkout under review;
* the policy, read from ``.theustad.json`` at that same commit; and
* a test census taken by running those tests on that commit's own tree.

The change's code is then run against the restored tests, in place, so the
dependencies the CI job installed are the ones the tests import.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Sequence

from . import census
from .chain import AuditChain
from .freezer import (
    DEFAULT_PATTERNS,
    Manifest,
    Tampering,
    check,
    freeze,
    freeze_commit,
    _matches,
    _normalize_patterns,
    _tree_entries,
    git_output,
    restore,
)
from .verifier import VerificationResult, default_argv, parse_command
from .verifier import run as run_verifier


CONFIG_NAME = ".theustad.json"
# A change that edits the workflow running this check, or the policy file it
# reads, is editing its own judge.
CI_PATTERNS = (*DEFAULT_PATTERNS, ".github/workflows/**", CONFIG_NAME)
DEFAULT_TIMEOUT = 1800.0
_CONFIG_TYPES: dict[str, tuple[type, ...]] = {
    "verifier": (str,),
    "protect": (list,),
    "protect_add": (list,),
    "census": (bool,),
    "timeout": (int, float),
}
_LIST_CAP = 50

VerifierRunner = Callable[[Sequence[str], Path, float], VerificationResult]
Output = Callable[[str], None]


class CIVerdict(str, Enum):
    VERIFIED = "VERIFIED"
    FALSIFIED = "FALSIFIED"
    TAMPERED = "TAMPERED"
    VERIFIER_TIMEOUT = "VERIFIER_TIMEOUT"


@dataclass(frozen=True)
class CIPolicy:
    verifier_argv: tuple[str, ...]
    patterns: tuple[str, ...]
    census: bool
    timeout: float
    source: str


@dataclass(frozen=True)
class ProtectedChanges:
    """What the change itself did to protected inputs, according to git."""

    modified: tuple[str, ...]
    deleted: tuple[str, ...]
    added: tuple[str, ...]

    @property
    def tampered(self) -> bool:
        # Adding a test is what an honest change usually does. Only editing or
        # removing one the change started from rewrites the acceptance oracle.
        return bool(self.modified or self.deleted)


@dataclass
class CIResult:
    verdict: CIVerdict
    exit_code: int
    base: str
    head: str
    pristine: str
    policy: CIPolicy
    protected_files: int
    changes: ProtectedChanges
    restored: Tampering
    census_armed: bool
    census_tests: int
    census_detail: str
    census_result: census.CensusResult | None
    verification: VerificationResult | None
    verifier_time_tampering: Tampering | None
    warnings: list[str] = field(default_factory=list)
    audit_log: Path | None = None
    audit_root: str | None = None

    def to_json(self) -> dict[str, Any]:
        verification = self.verification
        census_result = self.census_result
        return {
            "verdict": self.verdict.value,
            "exit_code": self.exit_code,
            "base": self.base,
            "head": self.head,
            "pristine": self.pristine,
            "policy": {
                "verifier": list(self.policy.verifier_argv),
                "patterns": list(self.policy.patterns),
                "census": self.policy.census,
                "timeout": self.policy.timeout,
                "source": self.policy.source,
            },
            "protected_files": self.protected_files,
            "changes": {
                "modified": list(self.changes.modified),
                "deleted": list(self.changes.deleted),
                "added_excluded": list(self.changes.added),
            },
            "working_tree_restored": _tamper_lists(self.restored),
            "census": {
                "armed": self.census_armed,
                "tests": self.census_tests,
                "detail": self.census_detail,
                "reason": census_result.reason if census_result else None,
                "missing": list(census_result.missing) if census_result else [],
            },
            "verifier": None
            if verification is None
            else {
                "argv": list(verification.argv),
                "exit_code": verification.exit_code,
                "timed_out": verification.timed_out,
                "tail": list(verification.tail),
            },
            "verifier_time_tampering": None
            if self.verifier_time_tampering is None
            else _tamper_lists(self.verifier_time_tampering),
            "warnings": list(self.warnings),
            "audit": {
                "log": str(self.audit_log) if self.audit_log else None,
                "root": self.audit_root,
            },
        }


def _tamper_lists(tampering: Tampering) -> dict[str, list[str]]:
    return {
        "modified": list(tampering.modified),
        "deleted": list(tampering.deleted),
        "added": list(tampering.added),
    }


def _git_text(repo: Path, *args: str) -> str:
    return git_output(repo, *args).decode("utf-8", errors="replace").strip()


def _commit(repo: Path, ref: str) -> str:
    # A ref is one argv element, so it cannot inject a shell; one that looks
    # like an option could still be read as one by git.
    if not ref or ref.startswith("-"):
        raise ValueError(f"not a commit reference: {ref!r}")
    return _git_text(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")


def _repository_root(repo: Path) -> Path:
    # Compared by identity, not spelling: git prints forward slashes on
    # Windows, and one directory can have more than one spelling.
    top = Path(_git_text(repo, "rev-parse", "--show-toplevel"))
    if not os.path.samefile(top, repo):
        raise ValueError(
            f"run the check from the repository root: {top} (not {repo})"
        )
    return repo


def _merge_base(repo: Path, base: str, head: str) -> str:
    try:
        return _git_text(repo, "merge-base", base, head)
    except RuntimeError as error:
        shallow = _git_text(repo, "rev-parse", "--is-shallow-repository")
        hint = (
            " The checkout is shallow; fetch full history (for example "
            "actions/checkout with fetch-depth: 0)."
            if shallow == "true"
            else ""
        )
        raise ValueError(
            f"the change and {base[:12]} share no history to compare against.{hint}"
        ) from error


def load_config(repo: Path, commit: str) -> dict[str, Any] | None:
    """Read ``.theustad.json`` as ``commit`` records it, or ``None``.

    Read from the commit the change started from, a policy file cannot be
    weakened by the change it is about to judge.
    """
    try:
        listing = git_output(repo, "ls-tree", "-z", commit, "--", CONFIG_NAME)
    except RuntimeError:
        return None
    if not listing:
        return None
    mode = listing.split(b" ", 1)[0].decode("ascii")
    if mode not in ("100644", "100755"):
        raise ValueError(f"{CONFIG_NAME} at {commit[:12]} is not a regular file")
    raw = git_output(repo, "show", f"{commit}:{CONFIG_NAME}")
    try:
        config = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{CONFIG_NAME} at {commit[:12]} is not valid JSON: {error}")
    if not isinstance(config, dict):
        raise ValueError(f"{CONFIG_NAME} must contain a JSON object")
    # A misspelt key in a security policy silently keeps the default, so an
    # unknown key is an error rather than something to ignore.
    unknown = sorted(set(config) - set(_CONFIG_TYPES))
    if unknown:
        raise ValueError(f"{CONFIG_NAME} has unknown keys: {', '.join(unknown)}")
    for key, value in config.items():
        expected = _CONFIG_TYPES[key]
        if isinstance(value, bool) and bool not in expected:
            raise ValueError(f"{CONFIG_NAME}: {key} has the wrong type")
        if not isinstance(value, expected):
            raise ValueError(f"{CONFIG_NAME}: {key} has the wrong type")
        if key in ("protect", "protect_add") and not all(
            isinstance(item, str) and item for item in value
        ):
            raise ValueError(f"{CONFIG_NAME}: {key} must be a list of patterns")
        if key == "timeout" and not (math.isfinite(value) and value > 0):
            raise ValueError(f"{CONFIG_NAME}: timeout must be a positive number")
        if key == "verifier" and not value.strip():
            raise ValueError(f"{CONFIG_NAME}: verifier cannot be empty")
    return config


def resolve_policy(
    repo: Path,
    config: dict[str, Any] | None,
    *,
    config_source: str,
    verifier: str | None = None,
    protect: Sequence[str] | None = None,
    protect_add: Sequence[str] = (),
    census_enabled: bool | None = None,
    timeout: float | None = None,
) -> CIPolicy:
    """Explicit options win, then the base commit's policy file, then defaults."""
    config = config or {}
    sources = []
    if config:
        sources.append(config_source)
    if any(
        value is not None
        for value in (verifier, protect, census_enabled, timeout)
    ) or protect_add:
        sources.append("command line")

    command = verifier if verifier is not None else config.get("verifier")
    verifier_argv = (
        parse_command(command, repo) if command is not None else default_argv()
    )
    base_patterns = (
        list(protect)
        if protect is not None
        else list(config.get("protect", CI_PATTERNS))
    )
    patterns = [*base_patterns, *config.get("protect_add", ()), *protect_add]
    if CONFIG_NAME not in patterns:
        patterns.append(CONFIG_NAME)
    return CIPolicy(
        verifier_argv=tuple(verifier_argv),
        patterns=tuple(dict.fromkeys(patterns)),
        census=census_enabled
        if census_enabled is not None
        else bool(config.get("census", True)),
        timeout=float(
            timeout if timeout is not None else config.get("timeout", DEFAULT_TIMEOUT)
        ),
        source=" + ".join(sources) if sources else "defaults",
    )


def protected_changes(
    repo: Path, pristine: str, head: str, patterns: Sequence[str]
) -> ProtectedChanges:
    """Compare protected entries between two commits, by git object id."""
    normalized = _normalize_patterns(patterns)

    def protected(commit: str) -> dict[str, tuple[str, str]]:
        return {
            path: (mode, object_id)
            for mode, _, object_id, path in _tree_entries(repo, commit)
            if _matches(path, normalized)
        }

    before = protected(pristine)
    after = protected(head)
    return ProtectedChanges(
        modified=tuple(
            sorted(path for path in before.keys() & after.keys() if before[path] != after[path])
        ),
        deleted=tuple(sorted(before.keys() - after.keys())),
        added=tuple(sorted(after.keys() - before.keys())),
    )


def _census_baseline(
    repo: Path,
    pristine: str,
    policy: CIPolicy,
    state_dir: Path,
    verifier_runner: VerifierRunner,
) -> tuple[dict[str, str] | None, int, str]:
    """Run the acceptance tests on the commit the change started from.

    The baseline must not come from the change's tree: a module-level skip the
    change added would shrink it, and the comparison would then find nothing
    missing.
    """
    if not policy.census:
        return None, 0, "disabled"
    if not census.is_pytest_verifier(policy.verifier_argv):
        return None, 0, "the verifier is not a recognisable pytest command"

    worktree = state_dir / f"pristine-{uuid.uuid4().hex[:12]}"
    report = state_dir / "census-baseline.xml"
    git_output(repo, "worktree", "add", "--detach", "--quiet", str(worktree), pristine)
    try:
        census.clear_report(report)
        verifier_runner(
            census.probe_argv(policy.verifier_argv, report),
            worktree,
            policy.timeout,
        )
        collected = census.parse_report(report)
        census.clear_report(report)
    finally:
        try:
            git_output(repo, "worktree", "remove", "--force", str(worktree))
        except RuntimeError:
            shutil.rmtree(worktree, ignore_errors=True)
            git_output(repo, "worktree", "prune")

    if not collected:
        return None, 0, "the base commit's test run wrote no report"
    carrying = census.required(collected)
    if not carrying:
        return None, 0, "the base commit's test run recorded no test that ran"
    return collected, len(carrying), ""


def _decide(
    changes: ProtectedChanges,
    verification: VerificationResult,
    verifier_time: Tampering,
    census_result: census.CensusResult | None,
) -> CIVerdict:
    if changes.tampered or verifier_time:
        return CIVerdict.TAMPERED
    if verification.timed_out:
        return CIVerdict.VERIFIER_TIMEOUT
    if verification.exit_code != 0 or census_result:
        return CIVerdict.FALSIFIED
    return CIVerdict.VERIFIED


def run_check(
    repo: str | os.PathLike[str],
    base: str,
    *,
    verifier: str | None = None,
    protect: Sequence[str] | None = None,
    protect_add: Sequence[str] = (),
    census_enabled: bool | None = None,
    timeout: float | None = None,
    state_dir: str | os.PathLike[str] | None = None,
    ephemeral: bool = False,
    verifier_runner: VerifierRunner = run_verifier,
    output: Output = print,
) -> CIResult:
    """Judge ``HEAD`` against the tests of its merge base with ``base``."""
    repository = _repository_root(Path(repo).resolve(strict=True))
    base_commit = _commit(repository, base)
    head_commit = _commit(repository, "HEAD")
    pristine = _merge_base(repository, base_commit, head_commit)

    config = load_config(repository, pristine)
    policy = resolve_policy(
        repository,
        config,
        config_source=f"{CONFIG_NAME} at {pristine[:12]}",
        verifier=verifier,
        protect=protect,
        protect_add=protect_add,
        census_enabled=census_enabled,
        timeout=timeout,
    )

    state = Path(
        state_dir if state_dir is not None else tempfile.mkdtemp(prefix="theustad-ci-")
    ).resolve(strict=False)
    state.mkdir(parents=True, exist_ok=True)
    manifest: Manifest = freeze_commit(repository, pristine, policy.patterns, state / "base")
    changes = protected_changes(repository, pristine, head_commit, policy.patterns)
    protected_files = sum(
        1 for entry in manifest.entries.values() if entry.file_type == "file"
    )
    warnings: list[str] = []

    audit = AuditChain(state / "logs")
    audit.append(
        round_number=0,
        kind="session",
        data={
            "mode": "ci",
            "base": base_commit,
            "head": head_commit,
            "pristine": pristine,
            "policy_source": policy.source,
            "verifier": list(policy.verifier_argv),
            "patterns": list(policy.patterns),
            "protected_files": protected_files,
        },
    )

    output(f"CI head {head_commit[:12]} against {pristine[:12]} (merge base with {base})")
    output(f"POLICY {policy.source}")
    output(f"VERIFIER {' '.join(policy.verifier_argv)}")
    output(f"PROTECTED {protected_files} files from {pristine[:12]}")
    if protected_files == 0:
        warning = (
            "THEUSTAD_WARNING NO_PROTECTED_INPUTS: no file at the base commit "
            "matches the protected patterns, so nothing stops the change from "
            "rewriting the tests. Set protect in .theustad.json."
        )
        warnings.append(warning)
        output(warning)
    if _git_text(repository, "status", "--porcelain", "--untracked-files=no"):
        warning = (
            "THEUSTAD_WARNING the working tree has uncommitted changes; the "
            "tests run against the files on disk, not against HEAD"
        )
        warnings.append(warning)
        output(warning)
    for label, paths in (("modified", changes.modified), ("deleted", changes.deleted)):
        if paths:
            output(f"CHANGED_PROTECTED {label} {', '.join(paths[:_LIST_CAP])}")
    if changes.added:
        output(
            "EXCLUDED added protected files are not part of the acceptance run: "
            + ", ".join(changes.added[:_LIST_CAP])
        )
    if changes.modified or changes.deleted or changes.added:
        audit.append(
            round_number=0,
            kind="tamper",
            data={
                "stage": "change",
                "modified": list(changes.modified),
                "deleted": list(changes.deleted),
                "added_excluded": list(changes.added),
            },
        )

    baseline, census_tests, census_detail = _census_baseline(
        repository, pristine, policy, state, verifier_runner
    )
    if baseline is not None:
        output(f"CENSUS {census_tests} acceptance tests ran at {pristine[:12]}")
    elif policy.census:
        warning = census.CENSUS_UNSUPERVISED.format(detail=census_detail)
        warnings.append(warning)
        output(warning)

    put_back: Manifest | None = None
    if not ephemeral:
        try:
            put_back = freeze(repository, policy.patterns, state / "working-tree")
        except ValueError as error:
            raise ValueError(
                f"cannot snapshot the working tree to put it back afterwards ({error}); "
                "run the check in a disposable checkout with --ephemeral"
            ) from error

    verification: VerificationResult | None = None
    census_result: census.CensusResult | None = None
    try:
        restored = check(repository, manifest)
        if restored:
            restore(repository, manifest)
            output(
                "RESTORED protected inputs from the base commit before verifying: "
                f"{len(restored.modified)} modified, {len(restored.deleted)} deleted, "
                f"{len(restored.added)} removed"
            )
        report = state / "census-report.xml"
        census.clear_report(report)
        verification = verifier_runner(
            census.report_argv(policy.verifier_argv, report)
            if baseline is not None
            else list(policy.verifier_argv),
            repository,
            policy.timeout,
        )
        verifier_time = check(repository, manifest)
        if verifier_time:
            output(
                "TAMPERED_DURING_VERIFY "
                + ", ".join(
                    [*verifier_time.modified, *verifier_time.deleted, *verifier_time.added][
                        :_LIST_CAP
                    ]
                )
            )
            audit.append(
                round_number=1,
                kind="tamper",
                data={"stage": "verifier", **_tamper_lists(verifier_time)},
            )
        if baseline is not None:
            census_result = census.compare(
                baseline, census.parse_report(report), verification.exit_code
            )
            census.clear_report(report)
    finally:
        if put_back is not None:
            restore(repository, put_back)

    for line in verification.tail:
        output(f"VERIFY | {line}")
    output(
        f"VERIFIER exit {verification.exit_code}"
        + (" TIMEOUT" if verification.timed_out else "")
    )
    if census_result:
        output(f"CENSUS_FAILED {census_result.reason}: {census_result.detail}")

    verdict = _decide(changes, verification, verifier_time, census_result)
    audit.append(
        round_number=1,
        kind="verdict",
        data={
            "verdict": verdict.value,
            "verifier_exit": verification.exit_code,
            "timed_out": verification.timed_out,
            "census": {
                "armed": baseline is not None,
                "tests": census_tests,
                "reason": census_result.reason if census_result else None,
                "detail": census_result.detail if census_result else census_detail,
            },
        },
    )
    for warning in warnings:
        audit.append(round_number=1, kind="warning", data={"message": warning})
    root = audit.append(round_number=1, kind="final", data={"verdict": verdict.value})

    output(f"FINAL {verdict.value}")
    output(f"AUDIT_LOG {audit.path}")
    output(f"AUDIT_ROOT {root}")
    return CIResult(
        verdict=verdict,
        exit_code=0 if verdict is CIVerdict.VERIFIED else 1,
        base=base_commit,
        head=head_commit,
        pristine=pristine,
        policy=policy,
        protected_files=protected_files,
        changes=changes,
        restored=restored,
        census_armed=baseline is not None,
        census_tests=census_tests,
        census_detail=census_detail,
        census_result=census_result,
        verification=verification,
        verifier_time_tampering=verifier_time if verifier_time else None,
        warnings=warnings,
        audit_log=audit.path,
        audit_root=root,
    )


_TITLES = {
    CIVerdict.VERIFIED: "VERIFIED: the base commit's acceptance tests pass, unedited, on this change",
    CIVerdict.FALSIFIED: "FALSIFIED: the base commit's acceptance tests do not pass on this change",
    CIVerdict.TAMPERED: "TAMPERED: this change edits the tests or configuration that judge it",
    CIVerdict.VERIFIER_TIMEOUT: "VERIFIER_TIMEOUT: the acceptance tests did not finish",
}


def _code_list(paths: Sequence[str]) -> list[str]:
    lines = [f"- `{path}`" for path in paths[:_LIST_CAP]]
    if len(paths) > _LIST_CAP:
        lines.append(f"- ... and {len(paths) - _LIST_CAP} more")
    return lines


def markdown_summary(result: CIResult) -> str:
    """A human summary, suitable for ``$GITHUB_STEP_SUMMARY``."""
    verification = result.verification
    if result.census_armed:
        census_line = f"{result.census_tests} acceptance tests ran at the base commit"
        if result.census_result:
            census_line += (
                f"; **{result.census_result.reason}**: {result.census_result.detail}"
            )
        else:
            census_line += "; every one ran again on this change"
    elif result.policy.census:
        census_line = f"not armed ({result.census_detail})"
    else:
        census_line = "disabled"
    lines = [
        f"## TheUstad {_TITLES[result.verdict]}",
        "",
        "| | |",
        "|---|---|",
        f"| Compared against | `{result.pristine[:12]}` (merge base) |",
        f"| Change | `{result.head[:12]}` |",
        f"| Verifier | `{' '.join(result.policy.verifier_argv)}`"
        + (f" (exit {verification.exit_code})" if verification else "")
        + " |",
        f"| Policy | {result.policy.source} |",
        f"| Protected inputs | {result.protected_files} files from the base commit |",
        f"| Test census | {census_line} |",
        "",
    ]
    if result.changes.modified or result.changes.deleted:
        lines.append("**Protected inputs this change edits** (restored before verifying):")
        lines.extend(_code_list([*result.changes.modified, *result.changes.deleted]))
        lines.append("")
    if result.verifier_time_tampering is not None:
        tampering = result.verifier_time_tampering
        lines.append("**Protected inputs changed while the tests ran:**")
        lines.extend(_code_list([*tampering.modified, *tampering.deleted, *tampering.added]))
        lines.append("")
    if result.changes.added:
        lines.append(
            "New protected files are left out of the acceptance run, so a new "
            "test cannot change how the existing ones behave:"
        )
        lines.extend(_code_list(result.changes.added))
        lines.append("")
    for warning in result.warnings:
        lines.append(f"> {warning}")
        lines.append("")
    if verification is not None and verification.tail:
        lines.append("<details><summary>Verifier output (last lines)</summary>")
        lines.append("")
        lines.append("```text")
        lines.extend(verification.tail)
        lines.append("```")
        lines.append("</details>")
        lines.append("")
    lines.append(f"Audit root `{result.audit_root}`")
    return "\n".join(lines) + "\n"
