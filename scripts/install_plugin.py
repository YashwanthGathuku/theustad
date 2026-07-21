#!/usr/bin/env python3
"""Install TheUstad into the personal Codex plugin marketplace."""

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
PLUGIN_NAME = "theustad"
PLUGIN_ID = "theustad@personal"
PACKAGE_ENTRIES = (
    ".codex-plugin",
    "skills",
    "scripts",
    "assets",
    "theustad.py",
    "theustadlib",
    "verify_chain.py",
    "LICENSE",
    "NOTICE",
    "README.md",
)
ProcessRunner = Callable[[list[str], Path | None], int]
Which = Callable[[str], str | None]


class InstallError(RuntimeError):
    """A safe local installation failure."""


def _load_plugin_manifest(source: Path, plugin_name: str) -> dict:
    manifest_path = source / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        raise InstallError(f"missing plugin.json under {source}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InstallError(f"invalid plugin.json under {source}") from error
    if not isinstance(payload, dict) or payload.get("name") != plugin_name:
        raise InstallError(f"plugin.json must identify the {plugin_name} plugin")
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


def _copy_package(
    source: Path,
    destination: Path,
    *,
    plugin_name: str,
    entries: Sequence[str],
) -> None:
    source_root = Path(source).expanduser().resolve(strict=True)
    target = _resolve_parent_only(destination)
    _load_plugin_manifest(source_root, plugin_name)
    if target == source_root or target.is_relative_to(source_root):
        raise InstallError("plugin destination must be outside the source checkout")

    package_items: list[tuple[str, Path]] = []
    for name in entries:
        item = source_root / name
        if not item.exists():
            raise InstallError(f"plugin package is missing required entry: {name}")
        _reject_package_symlinks(item)
        if not item.is_dir() and not item.is_file():
            raise InstallError(f"unsupported plugin package entry: {item}")
        package_items.append((name, item))

    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.with_name(f".{target.name}.{uuid.uuid4().hex}.staging")
    backup = target.with_name(f".{target.name}.{uuid.uuid4().hex}.backup")
    staging.mkdir(exist_ok=False)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
    try:
        for name, item in package_items:
            installed = staging / name
            if item.is_dir():
                shutil.copytree(item, installed, ignore=ignore)
            else:
                shutil.copy2(item, installed)

        had_target = target.is_symlink() or target.exists()
        if had_target:
            os.replace(target, backup)
        try:
            os.replace(staging, target)
        except OSError as install_error:
            if had_target:
                try:
                    os.replace(backup, target)
                except OSError as restore_error:
                    raise InstallError(
                        "plugin replacement failed; the previous installation "
                        f"is preserved at {backup}"
                    ) from restore_error
            raise install_error
        else:
            if had_target:
                _remove_existing(backup)
    finally:
        if staging.is_symlink() or staging.exists():
            _remove_existing(staging)


def copy_plugin(source: Path, destination: Path) -> None:
    _copy_package(
        source,
        destination,
        plugin_name=PLUGIN_NAME,
        entries=PACKAGE_ENTRIES,
    )


def _default_marketplace(name: str) -> dict:
    return {
        "name": name,
        "interface": {"displayName": "Personal"},
        "plugins": [],
    }


def _load_marketplace(path: Path, marketplace_name: str) -> dict:
    if path.is_symlink():
        raise InstallError(f"marketplace.json must not be a symlink: {path}")
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise InstallError(f"invalid marketplace JSON: {path}") from error
    else:
        payload = _default_marketplace(marketplace_name)
    if not isinstance(payload, dict):
        raise InstallError("marketplace.json must contain an object")
    if payload.get("name") != marketplace_name:
        raise InstallError(
            f"marketplace name must be {marketplace_name!r}, "
            f"got {payload.get('name')!r}"
        )
    plugins = payload.setdefault("plugins", [])
    if not isinstance(plugins, list):
        raise InstallError("marketplace.json field 'plugins' must be an array")
    return payload


def update_marketplace(
    path: Path,
    *,
    plugin_name: str,
    plugin_path: Path,
    marketplace_name: str = "personal",
) -> None:
    marketplace_path = _resolve_parent_only(path)
    if not plugin_name or Path(plugin_name).name != plugin_name:
        raise InstallError(f"invalid plugin name: {plugin_name!r}")
    installed_plugin = Path(plugin_path).expanduser().resolve(strict=False)
    expected_plugin = marketplace_path.parents[2] / "plugins" / plugin_name
    if installed_plugin != expected_plugin:
        raise InstallError(
            f"personal {plugin_name} plugin must be installed at {expected_plugin}"
        )

    payload = _load_marketplace(marketplace_path, marketplace_name)
    plugins = payload["plugins"]
    entry = {
        "name": plugin_name,
        "source": {"source": "local", "path": f"./plugins/{plugin_name}"},
        "policy": {
            "installation": "AVAILABLE",
            "authentication": "ON_INSTALL",
        },
        "category": "Developer Tools",
    }
    for index, current in enumerate(plugins):
        if isinstance(current, dict) and current.get("name") == plugin_name:
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
        prog="install-theustad-plugin",
        description="Install TheUstad into the personal Codex plugin marketplace.",
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
        destination = home / "plugins" / PLUGIN_NAME
        marketplace = home / ".agents" / "plugins" / "marketplace.json"
        codex_value = which("codex")
        if codex_value is None:
            raise InstallError("Codex CLI was not found on PATH")

        copy_plugin(source, destination)
        update_marketplace(
            marketplace,
            plugin_name=PLUGIN_NAME,
            plugin_path=destination,
        )

        print(f"THEUSTAD_PLUGIN_SOURCE {source}")
        print(f"THEUSTAD_PLUGIN_INSTALLED {destination}")
        print(f"THEUSTAD_PLUGIN_MARKETPLACE {marketplace}")
        return process_runner(
            [codex_value, "plugin", "add", PLUGIN_ID, "--json"],
            home,
        )
    except (InstallError, OSError) as error:
        print(f"THEUSTAD_PLUGIN_INSTALL_ERROR {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
