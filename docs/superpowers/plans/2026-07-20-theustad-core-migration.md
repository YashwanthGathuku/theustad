# TheUstad Core and Plugin Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make TheUstad 1.0.0 the canonical CLI, Python package, Codex plugin, and installation while preserving one release line of tested Gate compatibility.

**Architecture:** Move the current implementation into `theustad.py` and `theustadlib`, then keep `gate.py` and `gatelib` as forwarding adapters with no duplicated security logic. Rename the plugin and launcher canonically, migrate an existing Gate installation to a sibling forwarding plugin, and retain the v2 verdict and audit protocols unchanged.

**Tech Stack:** Python 3.10+, standard library, pytest, Codex personal plugins, JSON manifests, PowerShell and WSL 2 for acceptance.

## Global Constraints

- Product text uses `TheUstad`; executable, package, plugin, and path names use lowercase `theustad`; machine-readable prefixes use `THEUSTAD_*`.
- Preserve the complete `docs/SPEC.md` v2 security contract: trusted absolute Python, isolated mode, `shell=False`, process-group termination, exact thread-ID resume, pre/post manifest checks, timeout handling, and final-message claim classification.
- Verdict values and the SHA-256 audit record format remain byte-compatible.
- Runtime support remains Linux, macOS, and WSL 2; native Windows `doctor` and `run` fail closed.
- Runtime code remains Python standard-library-only; pytest remains the development and default-verifier dependency.
- Do not rewrite historical JSONL, captured output, video, checksum, or anchored-root evidence.
- Gate compatibility paths are deprecated adapters through TheUstad 1.x and contain no second runtime implementation.
- Use `apply_patch` for manual edits and `git mv` only for intentional tracked renames.

## File Map

- Create `theustad.py`: canonical CLI and round-loop implementation moved from `gate.py`.
- Create `theustadlib/`: canonical modules moved from `gatelib/`.
- Modify `gate.py`: deprecated executable and import adapter.
- Create `gatelib/`: deprecated package/module forwarding adapters.
- Create `scripts/theustad_plugin.py`: canonical plugin launcher moved from `scripts/gate_plugin.py`.
- Modify `scripts/gate_plugin.py`: deprecated launcher adapter.
- Modify `scripts/install_plugin.py`: canonical install plus existing-Gate migration.
- Modify `.codex-plugin/plugin.json`: TheUstad 1.0.0 metadata.
- Modify `skills/*/SKILL.md`: canonical `$theustad:*` instructions.
- Create `compat/gate-plugin/`: generated or copied forwarding plugin payload.
- Modify `scripts/build_plugin_assets.py` and `assets/*.png`: TheUstad-named asset constants and regenerated assets.
- Modify `tests/test_cli.py`, `tests/test_verdicts.py`, `tests/test_chain.py`, `tests/test_freezer.py`, `tests/test_session.py`, `tests/test_verifier.py`, and `tests/test_events.py`: canonical imports.
- Modify `tests/test_plugin_launcher.py` and `tests/test_plugin_package.py`: canonical plugin and migration behavior.
- Create `tests/test_legacy_compat.py`: compatibility equivalence and warnings.
- Create `tests/test_active_naming.py`: allowlisted active-name audit.
- Modify `docs/SPEC.md`: authoritative TheUstad product contract with former-name compatibility note.

---

### Task 1: Move the Python Core to Canonical Modules

**Files:**
- Rename: `gate.py` to `theustad.py`
- Rename: `gatelib/` to `theustadlib/`
- Modify: `theustad.py`
- Modify: `theustadlib/__init__.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_verdicts.py`
- Modify: `tests/test_chain.py`
- Modify: `tests/test_freezer.py`
- Modify: `tests/test_session.py`
- Modify: `tests/test_verifier.py`
- Modify: `tests/test_events.py`
- Modify: `tests/test_e2e_rehearsal.py`

**Interfaces:**
- Consumes: existing `GateRunner`, `GateResult`, `RoundResult`, `Verdict`, `default_argv`, `AgentSession`, `AuditChain`, and freezer APIs.
- Produces: the same signatures under `theustad` and `theustadlib`; later tasks may import only these canonical modules.

- [ ] **Step 1: Add canonical-import assertions before moving files**

Add to `tests/test_cli.py`:

```python
import importlib


def test_canonical_theustad_modules_are_importable():
    cli = importlib.import_module("theustad")
    freezer = importlib.import_module("theustadlib.freezer")

    assert cli.Verdict.VERIFIED.value == "VERIFIED"
    assert "tests/**" in freezer.DEFAULT_PATTERNS
```

- [ ] **Step 2: Run the new import test and require the expected failure**

Run:

```powershell
python -m pytest tests/test_cli.py::test_canonical_theustad_modules_are_importable -q
```

Expected: failure containing `ModuleNotFoundError: No module named 'theustad'`.

- [ ] **Step 3: Rename the tracked implementation and update canonical imports**

Run:

```powershell
git mv gate.py theustad.py
git mv gatelib theustadlib
```

Change the imports at the top of `theustad.py` to:

```python
from theustadlib.chain import AuditChain
from theustadlib.claims import Claim, find_claims
from theustadlib.freezer import DEFAULT_PATTERNS, Manifest, Tampering, check, freeze, restore
from theustadlib.session import DEFAULT_INITIAL_CMD, DEFAULT_RESUME_TEMPLATE, AgentSession, SessionResult
from theustadlib.verifier import VerificationResult, default_argv, parse_command as parse_verifier_command, run as run_verifier
```

Replace direct `gate` and `gatelib` imports in the listed tests with
`theustad` and `theustadlib`. Rename local helper `_gate()` to `_theustad()` and
the module variable passed to it accordingly; do not rename the public
`GateRunner` or `GateResult` classes in this release.

- [ ] **Step 4: Update canonical CLI branding without changing protocol values**

In `theustad.py`, use:

```python
"""TheUstad 1.0 command-line orchestrator."""

parser = argparse.ArgumentParser(
    prog="theustad.py",
    description="Verify coding-agent completion claims with protected evidence.",
)
```

Change human messages and state prefixes from Gate to TheUstad, including:

```python
"TheUstad detected protected-input tampering and restored the baseline. "
"TheUstad falsified the completion claim with the trusted verifier."
tempfile.mkdtemp(prefix="theustad-state-")
_console_output(f"THEUSTAD_ERROR {error}", stream=sys.stderr)
```

Keep these output records exact: `ROUND`, `FINAL`, `AUDIT_LOG`, and
`AUDIT_ROOT`.

- [ ] **Step 5: Run canonical core tests**

Run:

```powershell
python -m pytest tests/test_cli.py tests/test_verdicts.py tests/test_chain.py tests/test_freezer.py tests/test_session.py tests/test_verifier.py tests/test_events.py tests/test_e2e_rehearsal.py -q
```

Expected: all selected tests pass; POSIX-only tests may skip on native Windows.

- [ ] **Step 6: Commit the canonical core move**

```powershell
git add theustad.py theustadlib tests
git commit -m "refactor: make TheUstad the canonical runtime"
```

### Task 2: Add Tested Legacy Python Adapters

**Files:**
- Create: `gate.py`
- Create: `gatelib/__init__.py`
- Create: `gatelib/chain.py`
- Create: `gatelib/claims.py`
- Create: `gatelib/events.py`
- Create: `gatelib/freezer.py`
- Create: `gatelib/session.py`
- Create: `gatelib/verifier.py`
- Create: `tests/test_legacy_compat.py`

**Interfaces:**
- Consumes: canonical `theustad.main` and every public symbol in `theustadlib` modules.
- Produces: import-compatible `gate` and `gatelib.*` modules plus a `GATE_DEPRECATED` stderr record for executable use.

- [ ] **Step 1: Write failing legacy-equivalence tests**

Create `tests/test_legacy_compat.py`:

```python
import subprocess
import sys
from pathlib import Path

import gate
import theustad
from gatelib.chain import AuditChain as LegacyAuditChain
from theustadlib.chain import AuditChain


ROOT = Path(__file__).resolve().parents[1]


def test_legacy_imports_forward_to_canonical_objects():
    assert gate.GateRunner is theustad.GateRunner
    assert gate.Verdict is theustad.Verdict
    assert LegacyAuditChain is AuditChain


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
```

- [ ] **Step 2: Run the compatibility tests and require failure**

Run:

```powershell
python -m pytest tests/test_legacy_compat.py -q
```

Expected: collection failure because the adapters do not exist.

- [ ] **Step 3: Create the CLI adapter**

Create `gate.py`:

```python
#!/usr/bin/env python3
"""Deprecated Gate entry point forwarding to TheUstad."""

import sys

from theustad import *  # noqa: F401,F403
from theustad import main as _main


def main(argv=None):
    print("GATE_DEPRECATED use theustad.py", file=sys.stderr)
    return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Create package forwarding modules**

Use this exact form in each module, changing the canonical module name:

```python
"""Deprecated compatibility imports for TheUstad."""

from theustadlib.chain import *  # noqa: F401,F403
```

`gatelib/__init__.py` contains only its compatibility docstring. Do not copy
function bodies from `theustadlib`.

- [ ] **Step 5: Run compatibility and canonical regression tests**

Run:

```powershell
python -m pytest tests/test_legacy_compat.py tests/test_cli.py tests/test_verdicts.py tests/test_chain.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit compatibility adapters**

```powershell
git add gate.py gatelib tests/test_legacy_compat.py
git commit -m "feat: preserve Gate CLI and import compatibility"
```

### Task 3: Add Safe Project-Specific Protected Inputs

**Files:**
- Modify: `theustad.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_plugin_launcher.py`

**Interfaces:**
- Consumes: `theustadlib.freezer.DEFAULT_PATTERNS`.
- Produces: `_protected_patterns(overrides, additions) -> tuple[str, ...]` and repeatable `--protect-add PATTERN ...`.

- [ ] **Step 1: Write parser and merge tests**

Add to `tests/test_cli.py`:

```python
from theustad import _protected_patterns, build_parser
from theustadlib.freezer import DEFAULT_PATTERNS


def test_protect_add_appends_to_defaults_without_removing_them():
    assert _protected_patterns(None, [["package.json"], ["vitest.config.js"]]) == (
        *DEFAULT_PATTERNS,
        "package.json",
        "vitest.config.js",
    )


def test_protect_override_remains_exact_and_can_accept_additions():
    assert _protected_patterns([["spec/**"]], [["package.json"]]) == (
        "spec/**",
        "package.json",
    )


def test_parser_accepts_repeatable_protect_add():
    args = build_parser().parse_args(
        ["--repo", ".", "--protect-add", "package.json", "--protect-add", "vite.config.js"]
    )
    assert args.protect_add == [["package.json"], ["vite.config.js"]]
```

- [ ] **Step 2: Run the new tests and require missing-option failures**

Run:

```powershell
python -m pytest tests/test_cli.py -q
```

Expected: failures naming `_protected_patterns` or `--protect-add`.

- [ ] **Step 3: Implement additive pattern resolution**

Add to `theustad.py`:

```python
def _flatten_patterns(groups: Sequence[Sequence[str]] | None) -> tuple[str, ...]:
    return tuple(item for group in (groups or ()) for item in group)


def _protected_patterns(
    overrides: Sequence[Sequence[str]] | None,
    additions: Sequence[Sequence[str]] | None,
) -> tuple[str, ...]:
    base = _flatten_patterns(overrides) if overrides else DEFAULT_PATTERNS
    return (*base, *_flatten_patterns(additions))
```

Add the parser argument:

```python
parser.add_argument(
    "--protect-add",
    action="append",
    nargs="+",
    metavar="PATTERN",
    help="protected path pattern appended to the default or explicit set",
)
```

Replace the current `patterns` expression in `main` with:

```python
patterns = _protected_patterns(args.protect, args.protect_add)
```

- [ ] **Step 4: Run CLI, freezer, and verdict tests**

Run:

```powershell
python -m pytest tests/test_cli.py tests/test_freezer.py tests/test_verdicts.py -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit the safe extension option**

```powershell
git add theustad.py tests/test_cli.py
git commit -m "feat: append project-specific protected inputs"
```

### Task 4: Rename the Plugin Launcher and Environment Contract

**Files:**
- Rename: `scripts/gate_plugin.py` to `scripts/theustad_plugin.py`
- Create: `scripts/gate_plugin.py`
- Modify: `scripts/theustad_plugin.py`
- Modify: `tests/test_plugin_launcher.py`
- Modify: `tests/test_legacy_compat.py`

**Interfaces:**
- Consumes: canonical `theustad.py`, `THEUSTAD_STATE_HOME`, and repeatable `--protect-add` values.
- Produces: canonical launcher commands `doctor`, `run`, and `audit`; legacy launcher forwarding with `GATE_DEPRECATED`.

- [ ] **Step 1: Convert launcher tests to canonical imports and add environment precedence tests**

In `tests/test_plugin_launcher.py`, import from `scripts.theustad_plugin` and
replace Gate-named assertions with TheUstad values. Add:

```python
def test_theustad_state_home_wins_over_legacy_value(tmp_path):
    current = tmp_path / "current"
    legacy = tmp_path / "legacy"
    warnings = []
    assert default_state_home(
        environ={"THEUSTAD_STATE_HOME": str(current), "GATE_STATE_HOME": str(legacy)},
        warning=warnings.append,
    ) == current.resolve()
    assert warnings == []


def test_legacy_state_home_is_accepted_with_warning(tmp_path):
    legacy = tmp_path / "legacy"
    warnings = []
    assert default_state_home(
        environ={"GATE_STATE_HOME": str(legacy)}, warning=warnings.append
    ) == legacy.resolve()
    assert warnings == ["GATE_DEPRECATED use THEUSTAD_STATE_HOME"]
```

Extend the existing argv test with:

```python
assert argv[1].endswith("theustad.py")
assert argv[argv.index("--protect-add") + 1 :] == ["package.json", "package-lock.json"]
```

- [ ] **Step 2: Run launcher tests and require failures**

Run:

```powershell
python -m pytest tests/test_plugin_launcher.py -q
```

Expected: import or assertion failures for the not-yet-renamed launcher.

- [ ] **Step 3: Move and update the canonical launcher**

Run:

```powershell
git mv scripts/gate_plugin.py scripts/theustad_plugin.py
```

Use canonical constants and signatures:

```python
class PluginError(RuntimeError):
    """A user-actionable TheUstad plugin preflight failure."""


def default_state_home(*, environ=None, home=None, warning=print) -> Path:
    values = os.environ if environ is None else environ
    if values.get("THEUSTAD_STATE_HOME"):
        root = Path(values["THEUSTAD_STATE_HOME"])
    elif values.get("GATE_STATE_HOME"):
        warning("GATE_DEPRECATED use THEUSTAD_STATE_HOME")
        root = Path(values["GATE_STATE_HOME"])
    elif values.get("XDG_STATE_HOME"):
        root = Path(values["XDG_STATE_HOME"]) / "theustad"
    else:
        root = Path.home() if home is None else Path(home)
        root = root / ".local" / "state" / "theustad"
    return root.expanduser().resolve(strict=False)
```

Rename `build_gate_argv` to `build_theustad_argv`, `run_gate` to
`run_theustad`, point at `PLUGIN_ROOT / "theustad.py"`, pass each
`args.protect_add` value as `--protect-add`, and print `THEUSTAD_PLUGIN_*` and
`THEUSTAD_DOCTOR_*` records.

- [ ] **Step 4: Add the deprecated launcher adapter**

Create `scripts/gate_plugin.py`:

```python
#!/usr/bin/env python3
"""Deprecated Gate plugin launcher forwarding to TheUstad."""

import sys

from scripts.theustad_plugin import *  # noqa: F401,F403
from scripts.theustad_plugin import main as _main


def main(argv=None):
    print("GATE_DEPRECATED use scripts/theustad_plugin.py", file=sys.stderr)
    return _main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run launcher and compatibility tests**

Run:

```powershell
python -m pytest tests/test_plugin_launcher.py tests/test_legacy_compat.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit the launcher migration**

```powershell
git add scripts tests/test_plugin_launcher.py tests/test_legacy_compat.py
git commit -m "feat: make TheUstad the canonical plugin launcher"
```

### Task 5: Publish the Canonical Plugin and Upgrade Adapter

**Files:**
- Modify: `.codex-plugin/plugin.json`
- Modify: `scripts/install_plugin.py`
- Create: `compat/gate-plugin/.codex-plugin/plugin.json`
- Create: `compat/gate-plugin/skills/doctor/SKILL.md`
- Create: `compat/gate-plugin/skills/run/SKILL.md`
- Create: `compat/gate-plugin/skills/audit/SKILL.md`
- Create: `compat/gate-plugin/scripts/gate_plugin.py`
- Modify: `tests/test_plugin_package.py`

**Interfaces:**
- Consumes: canonical plugin root and `scripts/theustad_plugin.py`.
- Produces: `copy_plugin`, `update_marketplace`, `install_legacy_adapter`, and canonical `theustad@personal` registration.

- [ ] **Step 1: Rewrite package tests for TheUstad and add migration coverage**

Require manifest values:

```python
assert manifest["name"] == "theustad"
assert manifest["version"] == "1.0.0"
assert manifest["interface"]["displayName"] == "TheUstad"
assert manifest["repository"] == "https://github.com/YashwanthGathuku/theustad"
```

Require the canonical install call:

```python
assert calls == [
    (["/usr/bin/codex", "plugin", "add", "theustad@personal", "--json"], home)
]
assert (home / "plugins" / "theustad" / "theustad.py").is_file()
```

Add an upgrade test that seeds `~/plugins/gate`, invokes the installer, and
asserts that the resulting Gate package contains only its manifest, skills,
and forwarding script while `~/plugins/theustad/theustadlib` owns the core.

- [ ] **Step 2: Run package tests and require naming/migration failures**

Run:

```powershell
python -m pytest tests/test_plugin_package.py -q
```

Expected: failures for old manifest values, paths, and registration command.

- [ ] **Step 3: Update the canonical manifest**

Set `.codex-plugin/plugin.json` to version `1.0.0`, repository
`https://github.com/YashwanthGathuku/theustad`, homepage at the current Devpost
URL until its slug changes, display name `TheUstad`, and default prompt:

```json
"defaultPrompt": "Run this coding task through TheUstad and report the exact verdict and audit root."
```

- [ ] **Step 4: Refactor the installer around named package specifications**

Define:

```python
PLUGIN_NAME = "theustad"
PLUGIN_ID = "theustad@personal"
PACKAGE_ENTRIES = (
    ".codex-plugin", "skills", "scripts", "assets", "theustad.py",
    "theustadlib", "verify_chain.py", "LICENSE", "NOTICE", "README.md",
)
```

Make `update_marketplace` accept `plugin_name: str` and validate the sibling
path `plugins/<plugin_name>`. Install the canonical package first. If a prior
`plugins/gate` path or `gate` marketplace entry exists, copy
`compat/gate-plugin` to that path, preserve the marketplace slot, and invoke
`codex plugin add gate@personal --json` after the canonical registration.
Expose `--install-legacy-alias` to force this branch in a clean test home.

- [ ] **Step 5: Create the forwarding plugin package**

Use a `gate` manifest with version `1.0.0`, display name
`Gate (TheUstad compatibility)`, and a description that says it is deprecated.
Each skill must instruct Codex to invoke the adapter in this package. The
adapter resolves:

```python
canonical = Path(__file__).resolve().parents[2] / "theustad" / "scripts" / "theustad_plugin.py"
```

It rejects a missing canonical file, prints
`GATE_DEPRECATED use $theustad:<command>`, and executes
`[os.path.abspath(sys.executable), str(canonical), *sys.argv[1:]]` with
`shell=False`.

- [ ] **Step 6: Run installer and package tests**

Run:

```powershell
python -m pytest tests/test_plugin_package.py tests/test_plugin_launcher.py tests/test_legacy_compat.py -q
```

Expected: all selected tests pass; official validator test may skip when the
validator is unavailable.

- [ ] **Step 7: Commit plugin packaging**

```powershell
git add .codex-plugin scripts/install_plugin.py compat tests/test_plugin_package.py
git commit -m "feat: release the TheUstad 1.0 Codex plugin"
```

### Task 6: Rename Skills, Assets, and Legal Product Notices

**Files:**
- Modify: `skills/doctor/SKILL.md`
- Modify: `skills/run/SKILL.md`
- Modify: `skills/audit/SKILL.md`
- Modify: `scripts/build_plugin_assets.py`
- Modify: `assets/icon.png`
- Modify: `assets/logo.png`
- Modify: `NOTICE`
- Modify: `tests/test_plugin_package.py`

**Interfaces:**
- Consumes: canonical launcher path and plugin ID.
- Produces: self-contained TheUstad skills and deterministic branded PNG assets.

- [ ] **Step 1: Add exact skill and notice assertions**

Update package tests to require `scripts/theustad_plugin.py`, `TheUstad`,
`$theustad:run`, and the legal text:

```text
TheUstad 1.0 - originally developed by Yashwanth Gathuku
Formerly released as Gate v2
https://github.com/YashwanthGathuku/theustad
```

- [ ] **Step 2: Run package tests and require old-name failures**

```powershell
python -m pytest tests/test_plugin_package.py -q
```

Expected: assertions identify old active skill, launcher, asset-constant, and
NOTICE text.

- [ ] **Step 3: Update all canonical skill instructions**

Replace active Gate product references with TheUstad, invoke
`scripts/theustad_plugin.py`, retain the separate-child and exact-verdict
rules, and keep the native-Windows failure boundary. Do not change skill names
`doctor`, `run`, or `audit`; Codex namespaces them under the plugin ID.

- [ ] **Step 4: Update and regenerate assets**

Rename `GATE_GREEN` to `THEUSTAD_GREEN`, retain deterministic dimensions, and
change the mark from the gate outline to a compact `TU` monogram plus check.
Generate with:

```powershell
python scripts/build_plugin_assets.py
```

Expected: `assets/icon.png` is 128x128 and `assets/logo.png` is 512x512.

- [ ] **Step 5: Update NOTICE without changing LICENSE**

Name TheUstad as the current project, preserve the author and GPLv3 section
7(b) attribution, identify Gate v2 as the former release name, and point at the
renamed repository. Leave `LICENSE` byte-for-byte unchanged.

- [ ] **Step 6: Validate package, skills, assets, and legal files**

```powershell
python -m pytest tests/test_plugin_package.py -q
python "$HOME/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py" .
```

Expected: tests pass and validator prints `Plugin validation passed` when the
validator exists.

- [ ] **Step 7: Commit branded package surfaces**

```powershell
git add skills assets scripts/build_plugin_assets.py NOTICE tests/test_plugin_package.py
git commit -m "docs: brand plugin surfaces as TheUstad"
```

### Task 7: Update the Active Contract and Enforce Naming Boundaries

**Files:**
- Modify: `docs/SPEC.md`
- Modify: `docs/PROMPTS.md`
- Modify: `docs/RUNBOOK.md`
- Modify: `docs/BUILD_EVIDENCE.md`
- Create: `docs/evidence/LEGACY_GATE_EVIDENCE.md`
- Create: `tests/test_active_naming.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: the approved design and canonical file map.
- Produces: active TheUstad contract and a deterministic old-name allowlist.

- [ ] **Step 1: Write the active-name audit test**

Create `tests/test_active_naming.py` with an explicit tracked-file allowlist:

```python
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
    "gate.py",
    "fake_codex.py",
    "scripts/gate_plugin.py",
    "scripts/install_plugin.py",
    "README.md",
    "docs/SPEC.md",
    "docs/PLUGIN_GUIDE.md",
    "docs/BUILD_EVIDENCE.md",
    "docs/evidence/LEGACY_GATE_EVIDENCE.md",
    "tests/test_active_naming.py",
    "tests/test_docs_release.py",
    "tests/test_legacy_compat.py",
    "tests/test_plugin_package.py",
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
        if re.search(r"(?i)\bgate\b|GATE_", path.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(relative)
    assert offenders == []
```

- [ ] **Step 2: Run the naming test and capture the expected offender list**

```powershell
python -m pytest tests/test_active_naming.py -q
```

Expected: failure listing active source, tests, plugin metadata, and current
documentation that still use the old product name.

- [ ] **Step 3: Update active specification terminology carefully**

Change the product title and explanatory prose in `docs/SPEC.md` to TheUstad,
update canonical paths and commands, and add one compatibility subsection.
Do not change threat IDs, verdict values, record shapes, hash algorithm,
protected defaults, or the acceptance matrix. Update current instructions in
`docs/PROMPTS.md` and `docs/RUNBOOK.md`; retain dated output samples under the
legacy evidence policy.

- [ ] **Step 4: Add the legacy evidence index**

Document that existing Gate-named JSONL, console captures, videos, and hashes
were generated before the rename and are intentionally immutable. Include the
known anchored rehearsal root and state that future TheUstad roots are listed
separately.

- [ ] **Step 5: Update ignored runtime state**

Replace `.gate-state` with `.theustad-state` while retaining `.gate-state` as a
legacy ignored path:

```gitignore
.theustad-state/
.gate-state/
```

- [ ] **Step 6: Run the naming and complete test suites**

```powershell
python -m pytest tests/test_active_naming.py -q
python -m pytest tests -q
```

Expected: active-name audit passes; complete native suite passes with only
documented platform/validator skips.

- [ ] **Step 7: Commit the contract migration**

```powershell
git add docs/SPEC.md docs/PROMPTS.md docs/RUNBOOK.md docs/BUILD_EVIDENCE.md docs/evidence/LEGACY_GATE_EVIDENCE.md tests/test_active_naming.py .gitignore
git commit -m "docs: establish the TheUstad 1.0 contract"
```

### Task 8: Validate a Fresh TheUstad Installation in WSL 2

**Files:**
- Create after execution: `docs/evidence/theustad-1.0/plugin_install.txt`
- Create after execution: `docs/evidence/theustad-1.0/plugin_list.json`
- Create after execution: `docs/evidence/theustad-1.0/plugin_doctor.txt`

**Interfaces:**
- Consumes: committed TheUstad plugin package and WSL 2 Codex authentication.
- Produces: fresh-clone install/discovery evidence for the next plan.

- [ ] **Step 1: Update the local remote to the canonical URL and verify it**

```powershell
git remote set-url origin https://github.com/YashwanthGathuku/theustad.git
git remote -v
git ls-remote --symref origin HEAD
```

Expected: fetch and push URLs use `theustad.git`; remote HEAD resolves to
`refs/heads/master`.

- [ ] **Step 2: Run the complete suite in Ubuntu WSL 2**

```powershell
wsl.exe -d Ubuntu-24.04 -u gathu -- bash -lc 'cd /home/gathu/code/theustad && python3 -m pytest tests -q'
```

Expected: complete suite passes, including POSIX process-group tests.

- [ ] **Step 3: Install from the WSL checkout into a clean test home**

```bash
python3 -m venv "$HOME/.local/share/theustad/plugin-venv"
THEUSTAD_PYTHON="$HOME/.local/share/theustad/plugin-venv/bin/python"
"$THEUSTAD_PYTHON" -m pip install --upgrade pip pytest
"$THEUSTAD_PYTHON" scripts/install_plugin.py
codex plugin list --json
```

Expected: `theustad@personal` is installed and enabled; a fresh home does not
receive `gate@personal`.

- [ ] **Step 4: Run the supported plugin doctor and capture exact output**

```bash
THEUSTAD_STATE_HOME="$HOME/.local/state/theustad-release" \
"$THEUSTAD_PYTHON" "$HOME/plugins/theustad/scripts/theustad_plugin.py" \
  doctor --repo "$HOME/code/theustad" \
  2>&1 | tee docs/evidence/theustad-1.0/plugin_doctor.txt
```

Expected: `THEUSTAD_DOCTOR_OK` and exit code 0.

- [ ] **Step 5: Capture install and list evidence without editing old evidence**

Write the complete installer output to `plugin_install.txt` and the complete
JSON list output to `plugin_list.json`. Include commands, timestamps, Codex
version, Python version, and exit codes.

- [ ] **Step 6: Commit the installation evidence**

```powershell
git add docs/evidence/theustad-1.0
git commit -m "test: capture TheUstad 1.0 plugin installation"
```
