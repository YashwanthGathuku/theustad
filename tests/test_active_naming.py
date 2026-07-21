import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
# naming-audit: rule-definitions-start
OLD_NAME_RE = re.compile(r"(?i)\bgate\b|GATE_")

HISTORY_PREFIXES = (
    "docs/superpowers/",
)
HISTORY_FILES = {
    "docs/demo/README.md",
    "docs/demo/iniconfig_acceptance_test.py",
    "docs/demo/iniconfig_task.md",
    "docs/demo/prepare_wsl_demo.sh",
    "docs/demo/run_gate_cli_wsl.sh",
    "docs/demo/run_gate_plugin_wsl.sh",
    "docs/demo/run_no_gate_wsl.sh",
    "docs/schema_samples.jsonl",
    "docs/video/.gitignore",
    "docs/video/README.md",
    "docs/video/build_demo.ps1",
    "docs/video/build_live_narrated_demo.ps1",
    "docs/video/gate-real-project-live-narrated.en.srt",
    "docs/video/gate-real-project-live-narrated.mp4",
    "docs/video/gate-real-project-live.mp4",
    "docs/video/gate-v2-demo.mp4",
    "docs/video/record_live_comparison.ps1",
    "docs/video/render_demo.py",
    "docs/video/run_live_comparison_wsl.sh",
}
COMPATIBILITY_PREFIXES = (
    "compat/gate-plugin/",
    "gatelib/",
)
COMPATIBILITY_PATHS = {
    "gate.py",
    "scripts/gate_plugin.py",
    "tests/test_legacy_compat.py",
}

ALLOWED_SECTIONS = {
    "README.md": {
        "## Legacy Gate submission evidence",
        "## Legacy Gate real-project recording",
        "## Legacy Gate live Codex run",
        "## Gate 1.x compatibility",
    },
    "docs/PLUGIN_GUIDE.md": {"## Gate 1.x compatibility"},
    "docs/SPEC.md": {"### 3.1 TheUstad 1.x compatibility boundary"},
}
HISTORY_TAIL_MARKERS = {
    "docs/BUILD_EVIDENCE.md": "## Prompt 0 environment",
}
ALLOWED_FUNCTIONS = {
    "tests/test_active_naming.py": {
        "test_old_product_name_in_tracked_path_is_reported",
        "test_compatibility_allowance_does_not_hide_unlabelled_branding",
        "test_new_theustad_evidence_remains_scanned",
    },
    "tests/test_plugin_package.py": {
        "test_update_marketplace_replaces_gate_in_place",
        "test_installer_upgrades_existing_gate_to_forwarding_package",
        "test_installer_marketplace_gate_entry_triggers_upgrade_and_preserves_slot",
        "test_installer_flag_forces_legacy_alias_in_clean_home",
        "test_install_legacy_adapter_rejects_symlinked_package_entry",
        "test_legacy_adapter_warns_and_forwards_with_absolute_python",
        "test_legacy_adapter_rejects_missing_canonical_launcher",
        "test_legacy_gate_demo_documents_both_interfaces_and_honesty_boundaries",
    },
}
ALLOWED_LINE_PATTERNS = {
    ".codex-plugin/plugin.json": (
        r'\s*"(?:homepage|websiteURL)": "https://devpost\.com/software/gate-0lypv2",?',
    ),
    ".gitignore": (r"\.gate-state/",),
    "NOTICE": (r"\s*Formerly released as Gate v2",),
    "docs/BUILD_EVIDENCE.md": (
        r"verbatim historical evidence\. Their Gate-named paths, protocol samples, roots,",
        r"and outcomes are indexed in `docs/evidence/LEGACY_GATE_EVIDENCE\.md`; new",
    ),
    "docs/SPEC.md": (
        r"derive from his `evidence-gate` agent-discipline work\. Any public",
    ),
    "gate.py": (
        r'"""Deprecated Gate entry point forwarding to TheUstad\."""',
        r'\s*print\("GATE_DEPRECATED use theustad\.py", file=sys\.stderr\)',
    ),
    "scripts/gate_plugin.py": (
        r'"""Deprecated Gate plugin launcher forwarding to TheUstad\."""',
        r'\s*print\("GATE_DEPRECATED use scripts/theustad_plugin\.py", file=sys\.stderr\)',
    ),
    "scripts/install_plugin.py": (
        r'"""Install TheUstad and any required Gate compatibility alias\."""',
        r'LEGACY_PLUGIN_NAME = "gate"',
        r'LEGACY_PLUGIN_ID = "gate@personal"',
        r'\s*help="also install the deprecated gate@personal forwarding package",',
        r'\s*install_legacy_adapter\(source / "compat" / "gate-plugin", legacy_destination\)',
        r'\s*print\(f"GATE_PLUGIN_COMPAT_INSTALLED \{legacy_destination\}"\)',
    ),
    "scripts/theustad_plugin.py": (
        r'\s*elif values\.get\("GATE_STATE_HOME"\):',
        r'\s*warning\("GATE_DEPRECATED use THEUSTAD_STATE_HOME"\)',
        r'\s*root = Path\(values\["GATE_STATE_HOME"\]\)',
    ),
    "tests/test_events.py": (
        r'\s*\] == \["GATE_SCHEMA_PING"\]',
    ),
    "tests/test_plugin_launcher.py": (
        r'.*"GATE_STATE_HOME".*',
        r'.*"GATE_DEPRECATED use THEUSTAD_STATE_HOME".*',
    ),
    "tests/test_plugin_package.py": (
        r'.*https://devpost\.com/software/gate-0lypv2.*',
        r'.*Formerly released as Gate v2.*',
        r'.*assert not \(home / "plugins" / "gate"\)\.exists\(\).*',
        r'.*docs/video/gate-real-project-live\.mp4.*',
        r'.*GATE_DOCTOR_OK.*',
        r'.*SUPPORTED_GATE_RUN NOT RUN.*',
    ),
}
# naming-audit: rule-definitions-end


def tracked_files():
    return subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()


def is_legacy_evidence(relative):
    return relative.startswith("docs/evidence/") and not relative.startswith(
        "docs/evidence/theustad-1.0/"
    )


def is_history_path(relative):
    return (
        relative in HISTORY_FILES
        or relative.startswith(HISTORY_PREFIXES)
        or is_legacy_evidence(relative)
    )


def is_compatibility_path(relative):
    return relative in COMPATIBILITY_PATHS or relative.startswith(
        COMPATIBILITY_PREFIXES
    )


def line_is_allowed(
    relative,
    line,
    *,
    section,
    function_name,
    in_history_tail,
    in_rule_definitions,
):
    if in_history_tail or in_rule_definitions:
        return True
    if section in ALLOWED_SECTIONS.get(relative, set()):
        return True
    if function_name in ALLOWED_FUNCTIONS.get(relative, set()):
        return True
    return any(
        re.fullmatch(pattern, line)
        for pattern in ALLOWED_LINE_PATTERNS.get(relative, ())
    )


def find_offenders(files, *, root=ROOT):
    offenders = []
    for relative in files:
        if is_history_path(relative) or relative.startswith(COMPATIBILITY_PREFIXES):
            continue
        if relative == "tests/test_legacy_compat.py":
            continue

        if OLD_NAME_RE.search(relative) and not is_compatibility_path(relative):
            offenders.append(f"{relative}:path")

        path = root / relative
        if not path.is_file() or b"\0" in path.read_bytes()[:4096]:
            continue
        section = None
        function_name = None
        in_history_tail = False
        in_rule_definitions = False
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1
        ):
            if (
                relative == "tests/test_active_naming.py"
                and line == "# naming-audit: rule-definitions-start"
            ):
                in_rule_definitions = True
            if line.startswith("#"):
                section = line.strip()
            function_match = re.match(r"def (test_[a-zA-Z0-9_]+)\(", line)
            if function_match:
                function_name = function_match.group(1)
            if line == HISTORY_TAIL_MARKERS.get(relative):
                in_history_tail = True
            if OLD_NAME_RE.search(line) and not line_is_allowed(
                relative,
                line,
                section=section,
                function_name=function_name,
                in_history_tail=in_history_tail,
                in_rule_definitions=in_rule_definitions,
            ):
                offenders.append(f"{relative}:{line_number}:{line.strip()}")
            if (
                relative == "tests/test_active_naming.py"
                and line == "# naming-audit: rule-definitions-end"
            ):
                in_rule_definitions = False
    return offenders


def test_old_product_name_is_confined_to_compatibility_and_history():
    assert find_offenders(tracked_files()) == []


def test_old_product_name_in_tracked_path_is_reported(tmp_path):
    path = tmp_path / "gate-dashboard.md"
    path.write_text("Current product dashboard.\n", encoding="utf-8")

    assert find_offenders([path.name], root=tmp_path) == ["gate-dashboard.md:path"]


def test_compatibility_allowance_does_not_hide_unlabelled_branding(tmp_path):
    path = tmp_path / "gate.py"
    path.write_text(
        '"""Deprecated Gate entry point forwarding to TheUstad."""\n'
        'print("GATE_DEPRECATED use theustad.py", file=sys.stderr)\n'
        "Gate is the canonical product.\n",
        encoding="utf-8",
    )

    assert find_offenders([path.name], root=tmp_path) == [
        "gate.py:3:Gate is the canonical product."
    ]


def test_new_theustad_evidence_remains_scanned(tmp_path):
    relative = "docs/evidence/theustad-1.0/gate-dashboard.md"
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_text("Current product dashboard.\n", encoding="utf-8")

    assert find_offenders([relative], root=tmp_path) == [f"{relative}:path"]


def test_all_declared_path_exceptions_exist_in_git():
    files = set(tracked_files())
    declared_files = (
        HISTORY_FILES
        | COMPATIBILITY_PATHS
        | set(ALLOWED_SECTIONS)
        | set(HISTORY_TAIL_MARKERS)
        | set(ALLOWED_FUNCTIONS)
        | set(ALLOWED_LINE_PATTERNS)
    )
    assert sorted(declared_files - files) == []
    for prefix in HISTORY_PREFIXES + COMPATIBILITY_PREFIXES:
        assert any(relative.startswith(prefix) for relative in files), prefix
