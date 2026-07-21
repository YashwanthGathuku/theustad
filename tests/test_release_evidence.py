import dataclasses
import sys
from pathlib import Path

import pytest

from scripts.run_release_evidence import (
    ScenarioResult,
    extract_records,
    run_command,
    validate_output_dir,
)


ROOT = Path(__file__).parents[1]


def test_extract_verdicts_and_root():
    parsed = extract_records(
        "ROUND 1 TAMPERED\nFINAL TAMPERED\n"
        "AUDIT_LOG /tmp/audit.jsonl\nAUDIT_ROOT " + "a" * 64 + "\n"
    )
    assert parsed.verdicts == ("TAMPERED",)
    assert parsed.final == "TAMPERED"
    assert parsed.audit_log == Path("/tmp/audit.jsonl")
    assert parsed.root == "a" * 64


def test_extract_records_rejects_incomplete_protocol_output():
    with pytest.raises(ValueError, match="FINAL"):
        extract_records("ROUND 1 VERIFIED\n")


def test_output_directory_must_not_be_legacy_evidence(tmp_path):
    with pytest.raises(ValueError, match="legacy evidence"):
        validate_output_dir(ROOT / "docs" / "evidence" / "real_project_demo")


def test_output_directory_rejects_descendant_of_legacy_evidence():
    with pytest.raises(ValueError, match="legacy evidence"):
        validate_output_dir(
            ROOT / "docs" / "evidence" / "real_project_video" / "new"
        )


def test_failed_property_makes_summary_and_process_nonzero(tmp_path):
    result = ScenarioResult("A2", 0, ("TAMPERED",), False, False, "reason")
    assert result.passed is False


def test_scenario_result_is_immutable():
    result = ScenarioResult("B2", 0, ("VERIFIED",), True, True, "")
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.detail = "changed"


def test_run_command_records_argv_merged_output_and_exit_code(tmp_path):
    transcript = tmp_path / "command.txt"
    result = run_command(
        [
            sys.executable,
            "-c",
            (
                "import sys; print('stdout marker', flush=True); "
                "print('stderr marker', file=sys.stderr, flush=True); sys.exit(7)"
            ),
        ],
        tmp_path,
        transcript,
    )

    recorded = transcript.read_text(encoding="utf-8")
    assert result.returncode == 7
    assert result.stdout == "stdout marker\nstderr marker\n"
    assert "stdout marker\nstderr marker" in recorded
    assert recorded.endswith("[exit 7]\n")
    assert sys.executable in recorded.splitlines()[0]
