import ast
import subprocess
import sys
from pathlib import Path

import gate
import theustad
from scripts import gate_plugin, theustad_plugin
from gatelib.chain import AuditChain as LegacyAuditChain
from theustadlib.chain import AuditChain


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_imports_forward_to_canonical_objects():
    assert gate.GateRunner is theustad.TheUstadRunner
    assert gate.GateResult is theustad.TheUstadResult
    assert gate.Verdict is theustad.Verdict
    assert LegacyAuditChain is AuditChain


def test_canonical_runtime_defines_only_canonical_result_and_runner_classes():
    tree = ast.parse((ROOT / "theustad.py").read_text(encoding="utf-8"))
    class_names = {
        node.name for node in tree.body if isinstance(node, ast.ClassDef)
    }

    assert "TheUstadRunner" in class_names
    assert "TheUstadResult" in class_names
    assert "GateRunner" not in class_names
    assert "GateResult" not in class_names


def test_legacy_cli_emits_deprecation_and_canonical_help():
    result = subprocess.run(
        [sys.executable, str(ROOT / "gate.py"), "--help"],
        capture_output=True,
        text=True,
        shell=False,
        check=False,
    )
    assert result.returncode == 0
    assert "GATE_DEPRECATED use theustad.py" in result.stderr
    assert "Verify coding-agent completion claims" in result.stdout


def test_legacy_plugin_module_import_forwards_canonical_symbols():
    assert gate_plugin.build_theustad_argv is theustad_plugin.build_theustad_argv


def test_legacy_plugin_direct_execution_warns_and_forwards_help():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "gate_plugin.py"), "--help"],
        capture_output=True,
        text=True,
        shell=False,
        check=False,
    )

    assert result.returncode == 0
    assert "GATE_DEPRECATED use scripts/theustad_plugin.py" in result.stderr
    assert "Run the bundled TheUstad runtime" in result.stdout
