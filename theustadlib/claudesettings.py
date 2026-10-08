"""Install TheUstad's Claude Code hooks in user settings, and only there.

Hook mode keeps invocation authority in user-level configuration: a project's
own ``.claude/settings.json`` is part of the repository the agent edits. This
module edits the user file safely -- it refuses to rewrite a file it cannot
parse, keeps a backup, writes atomically, and touches no handler but its own.
"""

from __future__ import annotations

import copy
import json
import math
import os
import shlex
import shutil
import stat
from pathlib import Path
from typing import Any, Mapping

from .verifier import is_python_interpreter


HOOK_EVENTS = ("SessionStart", "Stop")
# One ceiling for every enrolled repository. Enrollment holds each verifier
# deadline, plus its margin, below it, so an installed handler can never be
# cancelled by the host while a verifier is still entitled to run -- and the
# installed hooks need no update when another repository is enrolled.
HANDLER_TIMEOUT = 3600
# What Claude Code applies to a command hook that names no timeout of its own.
CLAUDE_DEFAULT_COMMAND_TIMEOUT = 600
BACKUP_SUFFIX = ".theustad-backup"
PLUGIN_VENDOR = "claude-plugin"
_CLI_NAME = "theustad.py"


def user_settings_path(environ: Mapping[str, str] | None = None) -> Path:
    """Claude Code's user settings file, honouring ``CLAUDE_CONFIG_DIR``."""
    environment = os.environ if environ is None else environ
    configured = environment.get("CLAUDE_CONFIG_DIR")
    if configured:
        return Path(configured).expanduser() / "settings.json"
    try:
        home = Path.home()
    except RuntimeError as error:
        # Windows raises when neither USERPROFILE nor HOME is set; a hook or
        # enrollment launched with a minimal environment is not an error.
        raise ValueError(
            "cannot locate Claude Code's settings: no home directory; set "
            "CLAUDE_CONFIG_DIR or pass --settings"
        ) from error
    return home / ".claude" / "settings.json"


def in_plugin_cache(path: Path, environ: Mapping[str, str] | None = None) -> bool:
    """Whether ``path`` lives in Claude Code's plugin cache.

    That directory is versioned and replaced whenever the plugin updates, so
    nothing that outlives the plugin -- a settings hook above all -- may point
    into it.
    """
    try:
        cache = user_settings_path(environ).parent / "plugins" / "cache"
        Path(path).resolve().relative_to(cache.resolve())
    except ValueError:
        return False
    return True


def handler_event(handler: Any) -> str | None:
    """The event a settings handler runs TheUstad for, or ``None``."""
    if not isinstance(handler, dict) or handler.get("type") != "command":
        return None
    command = handler.get("command")
    if not isinstance(command, str):
        return None
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    if len(argv) < 4 or argv[-3:-1] != ["hook", "claude"]:
        return None
    if Path(argv[-4]).name != _CLI_NAME:
        return None
    return argv[-1] if argv[-1] in HOOK_EVENTS else None


def effective_timeout(handler: Mapping[str, Any]) -> float:
    """The timeout Claude Code will actually apply to ``handler``.

    A handler that names none, or names something unusable, gets the host's
    command-hook default -- not "no limit".
    """
    value = handler.get("timeout")
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        return float(CLAUDE_DEFAULT_COMMAND_TIMEOUT)
    return float(value)


def _inside(path: str, directory: str) -> bool:
    """Whether ``path``, or what it links to, lies under ``directory``."""
    root = Path(os.path.realpath(directory))
    for candidate in {os.path.abspath(path), os.path.realpath(path)}:
        try:
            Path(candidate).relative_to(root)
        except ValueError:
            continue
        return True
    return False


def runnable(
    handler: Mapping[str, Any], repository: str | os.PathLike[str] | None = None
) -> bool:
    """Whether a TheUstad settings handler will start, and start TheUstad.

    One that cannot start is worse than none: a missing interpreter exits
    127, which Claude Code treats as a non-blocking failure, so the stop goes
    through unverified.

    It has to be the command ``install-hooks`` writes, running code the
    repository under test cannot supply. Claude Code runs hooks in that
    repository, so a relative ``theustad.py`` -- or a relative interpreter,
    or a ``PATH`` entry such as ``.`` -- names whatever file the repository
    puts there, and a stub that exits 0 then answers for TheUstad. With
    ``repository`` given, a handler running from inside it does not count
    either: the agent being verified can edit that file.
    """
    try:
        argv = shlex.split(handler["command"])
    except (KeyError, TypeError, ValueError):
        return False
    # Exactly the shape ``handler`` writes. Anything before theustad.py can
    # stop it running -- ``python -c pass theustad.py ...`` runs only
    # ``pass`` -- and anything but Python there never runs it at all.
    if len(argv) != 5 or not is_python_interpreter(argv[0]):
        return False
    interpreter, cli = argv[0], argv[1]
    if not os.path.isabs(interpreter):
        if os.path.dirname(interpreter):
            return False
        interpreter = shutil.which(interpreter) or ""
    if not (os.path.isabs(interpreter) and os.path.isabs(cli)):
        return False
    if not (
        os.path.isfile(interpreter)
        and os.access(interpreter, os.X_OK)
        and os.path.isfile(cli)
    ):
        return False
    if repository is not None and (
        _inside(interpreter, repository) or _inside(cli, repository)
    ):
        return False
    return True


def installed_handlers(settings: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """TheUstad handlers in ``settings``, by event."""
    found: dict[str, list[dict[str, Any]]] = {}
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return found
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            handlers = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(handlers, list):
                continue
            for handler in handlers:
                if handler_event(handler) == event:
                    found.setdefault(event, []).append(handler)
    return found


def read_settings(path: Path) -> dict[str, Any]:
    """Parse a settings file; a missing or empty file is an empty object."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    try:
        settings = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"{path} is not valid JSON ({error}); fix it before installing hooks"
        ) from error
    if not isinstance(settings, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return settings


def handler(python: str, cli: str, event: str) -> dict[str, Any]:
    return {
        "type": "command",
        "command": shlex.join([python, cli, "hook", "claude", event]),
        "timeout": HANDLER_TIMEOUT,
    }


def _hooks_section(settings: dict[str, Any]) -> dict[str, Any]:
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError('"hooks" in Claude Code settings must be an object')
    return hooks


def _without_ours(groups: Any, event: str) -> list[Any]:
    if not isinstance(groups, list):
        raise ValueError(f'hooks "{event}" in Claude Code settings must be a list')
    kept = []
    for group in groups:
        handlers = group.get("hooks") if isinstance(group, dict) else None
        if not isinstance(handlers, list):
            kept.append(group)
            continue
        remaining = [item for item in handlers if handler_event(item) is None]
        if len(remaining) == len(handlers):
            kept.append(group)
        elif remaining:
            kept.append({**group, "hooks": remaining})
    return kept


def with_hooks(settings: Mapping[str, Any], python: str, cli: str) -> dict[str, Any]:
    """Return ``settings`` with exactly one TheUstad handler per event.

    Any earlier TheUstad handler -- from another checkout, or with an older
    timeout -- is replaced rather than joined, because two handlers for one
    session would run it twice.
    """
    updated = copy.deepcopy(dict(settings))
    hooks = _hooks_section(updated)
    for event in HOOK_EVENTS:
        groups = _without_ours(hooks.get(event, []), event)
        groups.append({"hooks": [handler(python, cli, event)]})
        hooks[event] = groups
    return updated


def without_hooks(settings: Mapping[str, Any]) -> dict[str, Any]:
    """Return ``settings`` with every TheUstad handler removed."""
    updated = copy.deepcopy(dict(settings))
    hooks = updated.get("hooks")
    if not isinstance(hooks, dict):
        return updated
    for event in list(hooks):
        if not isinstance(hooks[event], list):
            continue
        groups = _without_ours(hooks[event], event)
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]
    if not hooks:
        del updated["hooks"]
    return updated


def write_settings(path: Path, settings: Mapping[str, Any]) -> Path | None:
    """Write atomically, keeping one backup of the previous file.

    A settings file that is a symlink -- a dotfiles checkout, say -- is
    written through, so the link survives.
    """
    target = path.resolve() if path.is_symlink() else path
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    mode = None
    if target.exists():
        backup = target.with_name(target.name + BACKUP_SUFFIX)
        shutil.copy2(target, backup)
        mode = stat.S_IMODE(target.stat().st_mode)
    temporary = target.with_name(f".{target.name}.theustad-{os.getpid()}.tmp")
    temporary.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
    if mode is not None:
        os.chmod(temporary, mode)
    os.replace(temporary, target)
    return backup


def covers(
    event: str | None,
    environ: Mapping[str, str] | None = None,
    repository: str | os.PathLike[str] | None = None,
) -> bool:
    """Whether user settings already run TheUstad for ``event``.

    The Claude Code plugin ships the same hooks. When both are present the
    plugin's copy stands down, so one session is never handled twice. A file
    that cannot be read, or a handler that is not ``runnable`` for
    ``repository``, covers nothing: Claude Code cannot run hooks from the
    first, the second may not run TheUstad at all, and the plugin then has
    to.
    """
    if event not in HOOK_EVENTS:
        return False
    try:
        settings = read_settings(user_settings_path(environ))
    except (OSError, ValueError, UnicodeDecodeError):
        return False
    # Defer only to a handler that can start, from code the repository cannot
    # replace; anything less leaves the session with no enforcement at all.
    return any(
        runnable(item, repository)
        for item in installed_handlers(settings).get(event, [])
    )
