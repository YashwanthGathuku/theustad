import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_PREFIXES = (
    "compat/gate-plugin/",
    "docs/superpowers/",
    "gatelib/",
)
ALLOWED_FILES = {
    ".codex-plugin/plugin.json",
    ".gitignore",
    "NOTICE",
    "demo_repo/.gitignore",
    "gate.py",
    "fake_codex.py",
    "scripts/__init__.py",
    "scripts/gate_plugin.py",
    "scripts/install_plugin.py",
    "scripts/theustad_plugin.py",
    "README.md",
    "docs/SPEC.md",
    "docs/PLUGIN_GUIDE.md",
    "docs/BUILD_EVIDENCE.md",
    "docs/demo/README.md",
    "docs/demo/iniconfig_acceptance_test.py",
    "docs/demo/iniconfig_task.md",
    "docs/demo/prepare_wsl_demo.sh",
    "docs/demo/run_gate_cli_wsl.sh",
    "docs/demo/run_gate_plugin_wsl.sh",
    "docs/demo/run_no_gate_wsl.sh",
    "docs/evidence/LEGACY_GATE_EVIDENCE.md",
    "docs/schema_samples.jsonl",
    "docs/video/README.md",
    "docs/video/build_demo.ps1",
    "docs/video/build_live_narrated_demo.ps1",
    "docs/video/gate-real-project-live-narrated.en.srt",
    "docs/video/record_live_comparison.ps1",
    "docs/video/render_demo.py",
    "docs/video/run_live_comparison_wsl.sh",
    "tests/test_active_naming.py",
    "tests/test_docs_release.py",
    "tests/test_events.py",
    "tests/test_legacy_compat.py",
    "tests/test_plugin_launcher.py",
    "tests/test_plugin_package.py",
    "theustad.py",
    "theustadlib/freezer.py",
    "verify_chain.py",
}


def test_old_product_name_is_confined_to_compatibility_and_history():
    files = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    offenders = []
    for relative in files:
        if relative.startswith("docs/evidence/") and not relative.startswith(
            "docs/evidence/theustad-1.0/"
        ):
            continue
        if relative in ALLOWED_FILES or relative.startswith(ALLOWED_PREFIXES):
            continue
        path = ROOT / relative
        if not path.is_file() or b"\0" in path.read_bytes()[:4096]:
            continue
        if re.search(
            r"(?i)\bgate\b|GATE_",
            path.read_text(encoding="utf-8", errors="ignore"),
        ):
            offenders.append(relative)
    assert offenders == []
