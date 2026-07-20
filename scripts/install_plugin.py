#!/usr/bin/env python3
"""Install the local Gate package into the personal Codex marketplace."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ENTRIES = (
    ".codex-plugin",
    "skills",
    "scripts",
    "assets",
    "gate.py",
    "gatelib",
    "verify_chain.py",
    "LICENSE",
    "README.md",
)
ProcessRunner = Callable[[list[str], Path | None], int]
Which = Callable[[str], str | None]


class InstallError(RuntimeError):
    """A safe local installation failure."""


def _load_gate_manifest(source: Path) -> dict:
    manifest_path = source / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        raise InstallError(f"missing plugin.json under {source}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InstallError(f"invalid plugin.json under {source}") from error
    if not isinstance(payload, dict) or payload.get("name") != "gate":
        raise InstallError("plugin.json must identify the gate plugin")
    return payload


def _remove_existing(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _resolve_parent_only(path: Path) -> Path:
    expanded = Path(path).expanduser()
    return expanded.parent.resolve(strict=False) / expanded.name


def _reject_package_symlinks(path: Path) -> None:
    if path.is_symlink():
        raise InstallError(f"plugin package entries must not be symlinks: {path}")
    if not path.is_dir():
        return
    for candidate in path.rglob("*"):
        if candidate.is_symlink():
            raise InstallError(f"plugin package entries must not be symlinks: {candidate}")


def copy_plugin(source: Path, destination: Path) -> None:
    source_root = Path(source).expanduser().resolve(strict=True)
    target = _resolve_parent_only(destination)
    _load_gate_manifest(source_root)
    if target == source_root or target.is_relative_to(source_root):
        raise InstallError("plugin destination must be outside the source checkout")

    _remove_existing(target)
    target.mkdir(parents=True, exist_ok=False)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
    for name in PACKAGE_ENTRIES:
        item = source_root / name
        if not item.exists():
            raise InstallError(f"plugin package is missing required entry: {name}")
        _reject_package_symlinks(item)
        installed = target / name
        if item.is_dir():
            shutil.copytree(item, installed, ignore=ignore)
        elif item.is_file():
            shutil.copy2(item, installed)
        else:
            raise InstallError(f"unsupported plugin package entry: {item}")


def _default_marketplace(name: str) -> dict:
    return {
        "name": name,
        "interface": {"displayName": "Personal"},
        "plugins": [],
    }


def update_marketplace(
    path: Path,
    *,
    plugin_path: Path,
    marketplace_name: str = "personal",
) -> None:
    marketplace_path = _resolve_parent_only(path)
    installed_plugin = Path(plugin_path).expanduser().resolve(strict=False)
    expected_plugin = marketplace_path.parents[2] / "plugins" / "gate"
    if installed_plugin != expected_plugin:
        raise InstallError(
            f"personal Gate plugin must be installed at {expected_plugin}"
        )

    if marketplace_path.is_symlink():
        raise InstallError(f"marketplace.json must not be a symlink: {marketplace_path}")
    if marketplace_path.exists():
        try:
            payload = json.loads(marketplace_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise InstallError(f"invalid marketplace JSON: {marketplace_path}") from error
    else:
        payload = _default_marketplace(marketplace_name)
    if not isinstance(payload, dict):
        raise InstallError("marketplace.json must contain an object")
    if payload.get("name") != marketplace_name:
        raise InstallError(
            f"marketplace name must be {marketplace_name!r}, got {payload.get('name')!r}"
        )

    plugins = payload.setdefault("plugins", [])
    if not isinstance(plugins, list):
        raise InstallError("marketplace.json field 'plugins' must be an array")
    entry = {
        "name": "gate",
        "source": {"source": "local", "path": "./plugins/gate"},
        "policy": {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        },
        "category": "Developer Tools",
    }
    for index, current in enumerate(plugins):
        if isinstance(current, dict) and current.get("name") == "gate":
            plugins[index] = entry
            break
    else:
        plugins.append(entry)

    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = marketplace_path.with_name(
        f".{marketplace_path.name}.{uuid.uuid4().hex}.tmp"
    )
    try:
        temporary.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, marketplace_path)
    finally:
        if temporary.exists():
            temporary.unlink()


def run_process(argv: list[str], cwd: Path | None = None) -> int:
    return subprocess.run(
        argv,
        cwd=cwd,
        shell=False,
        check=False,
    ).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="install-gate-plugin",
        description="Install Gate into the personal Codex plugin marketplace.",
    )
    parser.add_argument("--source", type=Path, default=PLUGIN_ROOT)
    parser.add_argument("--home", type=Path, default=Path.home())
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    process_runner: ProcessRunner = run_process,
    which: Which = shutil.which,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        home = args.home.expanduser().resolve(strict=False)
        source = args.source.expanduser().resolve(strict=True)
        destination = home / "plugins" / "gate"
        marketplace = home / ".agents" / "plugins" / "marketplace.json"
        copy_plugin(source, destination)
        update_marketplace(marketplace, plugin_path=destination)

        codex_value = which("codex")
        if codex_value is None:
            raise InstallError("Codex CLI was not found on PATH")
        print(f"GATE_PLUGIN_SOURCE {source}")
        print(f"GATE_PLUGIN_INSTALLED {destination}")
        print(f"GATE_PLUGIN_MARKETPLACE {marketplace}")
        return process_runner(
            [codex_value, "plugin", "add", "gate@personal", "--json"],
            home,
        )
    except (InstallError, OSError) as error:
        print(f"GATE_PLUGIN_INSTALL_ERROR {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
