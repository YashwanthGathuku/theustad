"""TheUstad's Codex CLI hooks: where they live, and whether Codex will run them.

Codex reads user hooks from ``$CODEX_HOME/hooks.json`` (``~/.codex`` by
default) in the same shape as Claude Code's ``hooks`` section, so installing
reuses :mod:`claudesettings` with the ``codex`` vendor.  What differs is
trust: Codex runs a user hook only after the user has trusted it, by
recording a hash of the handler under ``[hooks.state]`` in ``config.toml``.
An installed but untrusted hook runs nothing and says nothing, so
:func:`trust_state` reports it rather than leaving "installed" to mean
"enforced".
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from . import claudesettings


VENDOR = "codex"
HOOK_EVENTS = claudesettings.HOOK_EVENTS
# Codex's default for a command hook with no timeout; it sets no ceiling for
# SessionStart or Stop.
CODEX_DEFAULT_COMMAND_TIMEOUT = 600
_EVENT_LABELS = {"SessionStart": "session_start", "Stop": "stop"}


def codex_home(environ: Mapping[str, str] | None = None) -> Path:
    environment = os.environ if environ is None else environ
    configured = environment.get("CODEX_HOME")
    if configured:
        return Path(configured).expanduser()
    try:
        return Path.home() / ".codex"
    except RuntimeError as error:
        raise ValueError(
            "cannot locate Codex's settings: no home directory; set CODEX_HOME "
            "or pass --settings"
        ) from error


def hooks_path(environ: Mapping[str, str] | None = None) -> Path:
    """Codex's user hooks file."""
    return codex_home(environ) / "hooks.json"


def handler_hash(event: str, handler: Mapping[str, Any], matcher: str | None) -> str:
    """The hash Codex records when a user trusts this handler.

    Codex hashes the handler as it normalises it -- the timeout filled in,
    ``async`` explicit -- with its event and matcher: SHA-256 over the
    key-sorted, compact JSON of that identity.  Checked against codex-cli
    0.162.1, which runs the hook without its bypass flag only when the stored
    hash equals this one.
    """
    timeout = handler.get("timeout")
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
        timeout = CODEX_DEFAULT_COMMAND_TIMEOUT
    normalized: dict[str, Any] = {
        "type": "command",
        "command": handler.get("command"),
        "timeout": timeout,
        "async": handler.get("async") is True,
    }
    if isinstance(handler.get("statusMessage"), str):
        normalized["statusMessage"] = handler["statusMessage"]
    identity: dict[str, Any] = {"event_name": _EVENT_LABELS[event], "hooks": [normalized]}
    if matcher is not None:
        identity["matcher"] = matcher
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _our_entries(path: Path, settings: Mapping[str, Any]):
    """(event, trust key, handler, matcher) for each TheUstad handler in the file."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return
    for event in HOOK_EVENTS:
        groups = hooks.get(event)
        if not isinstance(groups, list):
            continue
        for group_index, group in enumerate(groups):
            handlers = group.get("hooks") if isinstance(group, dict) else None
            if not isinstance(handlers, list):
                continue
            matcher = group.get("matcher") if isinstance(group.get("matcher"), str) else None
            for handler_index, item in enumerate(handlers):
                if claudesettings.handler_event(item, VENDOR) == event:
                    key = f"{path}:{_EVENT_LABELS[event]}:{group_index}:{handler_index}"
                    yield event, key, item, matcher


def _hook_states(config: Path) -> dict[str, Any] | None:
    """``[hooks.state]`` from Codex's config.toml; ``None`` when unreadable."""
    try:
        import tomllib
    except ImportError:  # Python 3.10 has no TOML reader.
        return None
    if not config.exists():
        return {}
    try:
        with config.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    features = data.get("features")
    if isinstance(features, dict) and features.get("hooks") is False:
        return {_HOOKS_OFF: True}
    hooks = data.get("hooks")
    states = hooks.get("state") if isinstance(hooks, dict) else None
    return states if isinstance(states, dict) else {}


# A key no hooks.json path can produce, marking `[features] hooks = false`.
_HOOKS_OFF = "\0hooks-off"


def trust_state(
    path: Path, settings: Mapping[str, Any], environ: Mapping[str, str] | None = None
) -> str:
    """``trusted``, ``untrusted``, ``modified``, ``disabled`` or ``unknown``.

    One answer for all of TheUstad's handlers: the least trusted one decides,
    because an untrusted Stop alone leaves every session unverified.
    """
    states = _hook_states(codex_home(environ) / "config.toml")
    if states is None:
        return "unknown"
    if states.get(_HOOKS_OFF):
        return "disabled"
    worst = "trusted"
    order = ("trusted", "modified", "untrusted", "disabled")
    keys_for = {str(path), str(Path(path).resolve())}
    for event, key, item, matcher in _our_entries(path, settings):
        state = None
        for prefix in keys_for:
            candidate = states.get(prefix + key[len(str(path)):])
            if isinstance(candidate, dict):
                state = candidate
                break
        if state is not None and state.get("enabled") is False:
            verdict = "disabled"
        elif state is None or not isinstance(state.get("trusted_hash"), str):
            verdict = "untrusted"
        elif state["trusted_hash"] == handler_hash(event, item, matcher):
            verdict = "trusted"
        else:
            verdict = "modified"
        if order.index(verdict) > order.index(worst):
            worst = verdict
    return worst
