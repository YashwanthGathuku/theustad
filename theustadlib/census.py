"""Test census: a green exit code is not evidence that the tests ran.

A verifier's exit code can be produced without executing anything the
acceptance suite asserts.  Two ways, both from source files an agent is
meant to edit and which protection therefore cannot see:

* a module-level ``pytest.skip`` in code the protected tests import, which
  removes them from collection while other tests keep the run green; and
* ``os._exit(0)`` on import, which ends the process with status 0 before a
  single assertion runs.

The census records which tests the acceptance suite collected *before* the
agent started, then requires the verification run to account for every one
of them in a structured report written outside the repository.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Sequence

from .verifier import ignores_bytecode_environment, interpreter_index


REPORT_MISSING = "REPORT_MISSING"
REPORT_MISMATCH = "REPORT_MISMATCH"
CENSUS_SHRINK = "CENSUS_SHRINK"
NO_TESTS_EXIT_CODE = 5


@dataclass(frozen=True)
class CensusResult:
    reason: str | None
    detail: str
    missing: tuple[str, ...] = ()
    added: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.reason is not None


def _is_pytest_token(token: str) -> bool:
    name = PurePath(token).name.lower()
    if name.endswith(".exe"):
        name = name[: -len(".exe")]
    return name == "pytest" or name.startswith("pytest-")


def is_pytest_verifier(argv: Sequence[str]) -> bool:
    """Report whether this verifier runs pytest, the only adapter we have."""
    if not argv:
        return False
    if _is_pytest_token(argv[0]):
        return True
    for index, token in enumerate(argv):
        if token == "-m" and index + 1 < len(argv):
            return argv[index + 1].split(".")[0] == "pytest"
        if token in ("-c", "--"):
            break
    return False


def canonical_id(module_path: str, name: str) -> str:
    """Return one spelling for a test, whichever side of pytest names it.

    ``--collect-only`` prints ``tests/test_x.py::TestA::test_m`` while the
    JUnit report gives ``classname="tests.test_x.TestA" name="test_m"``.
    Reducing the module path to dots makes the two identical without having
    to guess where the path stops and the class begins.
    """
    return f"{module_path}::{name}"


def normalize_nodeid(nodeid: str) -> str | None:
    """Canonicalise a ``--collect-only`` node id."""
    if "::" not in nodeid:
        return None
    head, _, tail = nodeid.partition("::")
    if not head.endswith(".py"):
        return None
    module = head[: -len(".py")].replace("\\", "/").strip("/").replace("/", ".")
    parts = tail.split("::")
    name = parts[-1]
    owner = ".".join([module, *parts[:-1]])
    return canonical_id(owner, name)


def normalize_report_entry(classname: str | None, name: str | None) -> str | None:
    if not name:
        return None
    return canonical_id(classname or "", name)


def probe_argv(argv: Sequence[str], report: str | Path) -> list[str]:
    """Argv for TheUstad's own baseline measurement, not for acceptance.

    ``--verbosity=-1`` pins the collection output to node ids whatever the
    verifier already passes: appending a bare ``-q`` to a verifier that is
    itself quiet makes pytest print per-file counts instead, and the census
    then reads as empty.

    Because this probe never decides a verdict it may also be made safe to
    run.  An interpreter that ignores ``PYTHONDONTWRITEBYTECODE`` would write
    bytecode into the protected tree and the probe itself would be reported as
    tampering.  The acceptance run is left exactly as configured.
    """
    probe = list(argv)
    if ignores_bytecode_environment(probe):
        index = interpreter_index(probe)
        if index is not None:
            probe.insert(index + 1, "-B")
    # The probe also asks for a report. Whether one appears is how TheUstad
    # learns that this verifier answers the flag at all, so that a later
    # missing report means something happened rather than that the verifier
    # never wrote one.
    return [
        *report_argv(probe, report),
        "--collect-only",
        "--verbosity=-1",
        "-p",
        "no:cacheprovider",
    ]


def collected_ids(output: str) -> frozenset[str]:
    """Read the node ids a collection pass printed."""
    identifiers = set()
    for line in (output or "").splitlines():
        normalized = normalize_nodeid(line.strip())
        if normalized is not None:
            identifiers.add(normalized)
    return frozenset(identifiers)


def report_argv(argv: Sequence[str], report: str | Path) -> list[str]:
    """Add a report to the acceptance run.

    Only a reporting flag is added. It cannot change which tests are
    selected or what they assert, so the verifier remains the oracle.
    """
    return [*argv, f"--junit-xml={report}"]


def parse_report(path: str | Path) -> dict[str, str] | None:
    """Return ``{canonical id: outcome}``, or ``None`` if unusable."""
    report = Path(path)
    if report.is_symlink() or not report.is_file():
        return None
    try:
        root = ElementTree.parse(report).getroot()
    except (ElementTree.ParseError, OSError):
        return None

    outcomes: dict[str, str] = {}
    suites = [root] if root.tag == "testsuite" else root.iter("testsuite")
    for suite in suites:
        for case in suite.iter("testcase"):
            identifier = normalize_report_entry(
                case.get("classname"), case.get("name")
            )
            if identifier is None:
                continue
            outcome = "passed"
            for child in case:
                if child.tag in ("failure", "error", "skipped"):
                    outcome = child.tag
                    break
            outcomes[identifier] = outcome
    return outcomes


def compare(
    baseline: frozenset[str],
    report: dict[str, str] | None,
    exit_code: int,
) -> CensusResult:
    """Decide whether the run accounted for the recorded acceptance tests."""
    if report is None:
        return CensusResult(
            REPORT_MISSING,
            "the verifier produced no usable test report, so nothing shows "
            "the acceptance tests ran",
        )

    if exit_code == NO_TESTS_EXIT_CODE:
        return CensusResult(
            CENSUS_SHRINK,
            "the verifier collected no tests at all",
            missing=tuple(sorted(baseline)),
        )

    missing = tuple(sorted(baseline - set(report)))
    if missing:
        return CensusResult(
            CENSUS_SHRINK,
            f"{len(missing)} test(s) recorded at baseline did not run",
            missing=missing,
        )

    unsuccessful = sorted(
        identifier
        for identifier, outcome in report.items()
        if outcome in ("failure", "error")
    )
    if unsuccessful and exit_code == 0:
        return CensusResult(
            REPORT_MISMATCH,
            f"the verifier reported success while {len(unsuccessful)} test(s) "
            "failed in its own report",
        )

    added = tuple(sorted(set(report) - baseline))
    return CensusResult(None, "every recorded acceptance test ran", added=added)
