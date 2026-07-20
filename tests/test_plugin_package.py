from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.build_plugin_assets import build_assets
from scripts.install_plugin import (
    InstallError,
    copy_plugin,
    main as install_main,
    update_marketplace,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / ".codex-plugin" / "plugin.json"
SKILL_NAMES = ("run", "doctor", "audit")


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


def test_manifest_identifies_gate_and_only_bundles_skills():
    manifest = load_manifest()

    assert manifest["name"] == "gate"
    assert manifest["version"] == "0.1.0"
    assert manifest["skills"] == "./skills/"
    assert manifest["license"] == "MIT"
    assert {"hooks", "mcpServers", "apps"}.isdisjoint(manifest)


def test_manifest_metadata_and_asset_paths_exist():
    manifest = load_manifest()
    interface = manifest["interface"]

    assert interface["displayName"] == "Gate"
    assert interface["category"] == "Developer Tools"
    assert interface["defaultPrompt"]
    for field in ("composerIcon", "logo"):
        value = interface[field]
        assert value.startswith("./assets/")
        assert (ROOT / value).is_file()


@pytest.mark.parametrize("name", SKILL_NAMES)
def test_each_skill_has_frontmatter_and_launcher_command(name):
    text = (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")

    assert text.startswith("---\n")
    assert f"name: {name}\n" in text
    assert "description:" in text.split("---", 2)[1]
    assert "scripts/gate_plugin.py" in text
    assert "absolute" in text.lower()


def test_run_skill_preserves_gate_as_the_verdict_authority():
    text = (ROOT / "skills" / "run" / "SKILL.md").read_text(encoding="utf-8")

    assert "Do not edit the target repository" in text
    assert "FINAL VERIFIED" in text
    assert "exit code 0" in text
    assert "Do not reinterpret" in text
    assert "separate Gate-controlled child" in text


def test_generated_png_assets_have_expected_dimensions(tmp_path):
    build_assets(tmp_path)

    assert png_dimensions(tmp_path / "icon.png") == (128, 128)
    assert png_dimensions(tmp_path / "logo.png") == (512, 512)


def test_committed_png_assets_have_expected_dimensions():
    assert png_dimensions(ROOT / "assets" / "icon.png") == (128, 128)
    assert png_dimensions(ROOT / "assets" / "logo.png") == (512, 512)


def test_official_plugin_validator_accepts_package():
    configured = os.environ.get("GATE_PLUGIN_VALIDATOR")
    validator = (
        Path(configured)
        if configured
        else Path.home()
        / ".codex"
        / "skills"
        / ".system"
        / "plugin-creator"
        / "scripts"
        / "validate_plugin.py"
    )
    if not validator.is_file():
        pytest.skip("Codex plugin validator is not installed")

    result = subprocess.run(
        [sys.executable, str(validator), str(ROOT)],
        capture_output=True,
        text=True,
        shell=False,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Plugin validation passed" in result.stdout


def write_marketplace(path: Path, plugins: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "name": "personal",
                "interface": {"displayName": "Personal"},
                "plugins": plugins,
                "custom": {"preserve": True},
            }
        ),
        encoding="utf-8",
    )


def test_copy_plugin_uses_allowlist_and_excludes_repo_and_cache_content(tmp_path):
    destination = tmp_path / "home" / "plugins" / "gate"

    copy_plugin(ROOT, destination)

    assert (destination / "gate.py").is_file()
    assert (destination / "gatelib" / "session.py").is_file()
    assert (destination / "skills" / "run" / "SKILL.md").is_file()
    assert not (destination / ".git").exists()
    assert not (destination / "tests").exists()
    assert not list(destination.rglob("__pycache__"))
    assert not list(destination.rglob("*.pyc"))


def test_copy_plugin_replaces_stale_destination_content(tmp_path):
    destination = tmp_path / "home" / "plugins" / "gate"
    destination.mkdir(parents=True)
    (destination / ".mcp.json").write_text("{}", encoding="utf-8")

    copy_plugin(ROOT, destination)

    assert not (destination / ".mcp.json").exists()
    assert (destination / ".codex-plugin" / "plugin.json").is_file()


def test_copy_plugin_replaces_destination_symlink_without_following_it(tmp_path):
    victim = tmp_path / "victim"
    victim.mkdir()
    marker = victim / "keep.txt"
    marker.write_text("do not delete", encoding="utf-8")
    destination = tmp_path / "plugins" / "gate"
    destination.parent.mkdir()
    try:
        destination.symlink_to(victim, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlinks unavailable: {error}")

    copy_plugin(ROOT, destination)

    assert marker.read_text(encoding="utf-8") == "do not delete"
    assert destination.is_dir()
    assert not destination.is_symlink()
    assert (destination / ".codex-plugin" / "plugin.json").is_file()


def test_copy_plugin_does_not_resolve_final_destination_component(
    tmp_path, monkeypatch
):
    destination = tmp_path / "plugins" / "gate"
    destination.parent.mkdir()
    original_resolve = Path.resolve

    def guarded_resolve(path, *args, **kwargs):
        if path == destination:
            raise AssertionError("final destination component was resolved")
        return original_resolve(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", guarded_resolve)

    copy_plugin(ROOT, destination)

    assert (destination / ".codex-plugin" / "plugin.json").is_file()


def test_copy_plugin_rejects_symlinked_package_entry(tmp_path, monkeypatch):
    destination = tmp_path / "plugins" / "gate"
    symlinked_entry = ROOT / "gate.py"
    original_is_symlink = Path.is_symlink

    def fake_is_symlink(path):
        if path == symlinked_entry:
            return True
        return original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)

    with pytest.raises(InstallError, match="symlink"):
        copy_plugin(ROOT, destination)


def test_copy_plugin_rejects_source_without_gate_manifest(tmp_path):
    source = tmp_path / "empty"
    source.mkdir()

    with pytest.raises(InstallError, match="plugin.json"):
        copy_plugin(source, tmp_path / "plugins" / "gate")


def test_update_marketplace_preserves_unrelated_plugins_and_top_level_keys(tmp_path):
    path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    other = {
        "name": "other",
        "source": {"source": "local", "path": "./plugins/other"},
    }
    write_marketplace(path, [other])

    update_marketplace(path, plugin_path=tmp_path / "plugins" / "gate")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["custom"] == {"preserve": True}
    assert [entry["name"] for entry in payload["plugins"]] == ["other", "gate"]
    gate = payload["plugins"][1]
    assert gate["source"] == {"source": "local", "path": "./plugins/gate"}
    assert gate["policy"]["installation"] == "AVAILABLE"


def test_update_marketplace_replaces_gate_in_place(tmp_path):
    path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    write_marketplace(
        path,
        [
            {"name": "before"},
            {"name": "gate", "source": {"source": "local", "path": "old"}},
            {"name": "after"},
        ],
    )

    update_marketplace(path, plugin_path=tmp_path / "plugins" / "gate")

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert [entry["name"] for entry in payload["plugins"]] == [
        "before",
        "gate",
        "after",
    ]
    assert payload["plugins"][1]["source"]["path"] == "./plugins/gate"


def test_update_marketplace_rejects_symlinked_manifest(tmp_path, monkeypatch):
    path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    plugin_path = tmp_path / "plugins" / "gate"
    original_is_symlink = Path.is_symlink

    def fake_is_symlink(candidate):
        if candidate == path:
            return True
        return original_is_symlink(candidate)

    monkeypatch.setattr(Path, "is_symlink", fake_is_symlink)

    with pytest.raises(InstallError, match="symlink"):
        update_marketplace(path, plugin_path=plugin_path)


def test_installer_invokes_codex_plugin_add_with_argv(tmp_path):
    home = tmp_path / "home"
    calls = []

    def process_runner(argv, cwd):
        calls.append((argv, cwd))
        return 0

    result = install_main(
        ["--source", str(ROOT), "--home", str(home)],
        process_runner=process_runner,
        which=lambda name: "/usr/bin/codex" if name == "codex" else None,
    )

    assert result == 0
    assert calls == [
        (["/usr/bin/codex", "plugin", "add", "gate@personal", "--json"], home)
    ]
    assert (home / "plugins" / "gate" / "gate.py").is_file()
    marketplace = json.loads(
        (home / ".agents" / "plugins" / "marketplace.json").read_text()
    )
    assert marketplace["plugins"][0]["name"] == "gate"


def test_readme_documents_complete_plugin_workflow_and_platform_boundary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    for required in (
        "## Codex plugin",
        "python3 scripts/install_plugin.py",
        "$gate:doctor",
        "$gate:run",
        "$gate:audit",
        "codex plugin remove gate@personal --json",
        "Linux, macOS, or WSL 2",
        "Native Windows",
        "separate Gate-controlled child",
        "## Choose an interface",
        "Standalone CLI",
        "docs/demo/README.md",
    ):
        assert required in readme


def test_real_project_demo_documents_both_interfaces_and_honesty_boundaries():
    demo = (ROOT / "docs" / "demo" / "README.md").read_text(encoding="utf-8")

    for required in (
        "pytest-dev/iniconfig",
        "77db208ab4ae0cd2061d909fe222a1db72867850",
        "human-authored acceptance test",
        "$gate:doctor",
        "$gate:run",
        "$gate:audit",
        "gate.py --repo",
        "Linux, macOS, or WSL 2",
        "not an existing upstream issue",
    ):
        assert required in demo


def test_plugin_evidence_records_validation_installation_and_fresh_skill_run():
    evidence = ROOT / "docs" / "evidence"

    validation = (evidence / "plugin_validation.txt").read_text(encoding="utf-8")
    installation = (evidence / "plugin_install.txt").read_text(encoding="utf-8")
    skill_audit = (evidence / "plugin_skill_audit.txt").read_text(
        encoding="utf-8"
    )
    real_demo = (evidence / "real_project_demo_prep.txt").read_text(
        encoding="utf-8"
    )

    assert "Exit code: 0" in validation
    assert "Plugin validation passed" in validation
    assert "installed: true" in installation
    assert "enabled: true" in installation
    assert "DOCTOR_EXIT 2" in installation
    assert "Thread: 019f80bd-68ce-7452-b995-a3f708981852" in skill_audit
    assert "Validator exit code: 0" in skill_audit
    assert "1 failed, 49 passed" in real_demo
    assert "SUPPORTED_GATE_RUN NOT RUN" in real_demo

    expected_root = (
        "200042504cd90869d2bc8edcd60278049e231ead88ae69a60919a64a335d4a20"
    )
    assert expected_root in installation
    assert expected_root in skill_audit
