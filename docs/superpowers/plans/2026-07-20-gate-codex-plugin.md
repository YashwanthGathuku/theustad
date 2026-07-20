# Gate Codex Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the completed Gate v2 runtime as an installable Codex plugin with `run`, `doctor`, and `audit` skills, a deterministic launcher, and a safe local installer.

**Architecture:** The repository root is the plugin root. Codex installs a copy outside target repositories; the skills invoke a Python adapter that delegates all security-sensitive behavior to the existing `gate.py` core. The adapter adds platform and dependency preflight, unambiguous task inputs, persistent external state paths, and audit invocation without changing Gate verdict semantics.

**Tech Stack:** Python 3.10+ standard library, pytest, Codex plugin manifest and Agent Skills, Codex CLI plugin marketplace.

## Global Constraints

- Preserve every security and verdict requirement in `docs/SPEC.md`.
- Runtime code uses only the Python standard library; pytest remains the development and default verifier dependency.
- Gate runs on Linux, macOS, and WSL 2; native Windows must fail closed before starting a child agent.
- Use argv lists with `shell=False`; never assemble shell pipelines or redirections.
- The installed runtime, task copy, snapshots, and audit logs must remain outside the target repository.
- Do not add hooks, MCP servers, app connectors, native Windows process control, remote services, or verifier auto-detection.
- Use mutually exclusive `--task-text` and `--task-file` inputs.
- Only the existing Gate `VERIFIED` verdict exits zero.
- Every production-code behavior follows red-green-refactor.

## File Map

- `scripts/gate_plugin.py`: deterministic `doctor`, `run`, and `audit` adapter.
- `scripts/install_plugin.py`: copies an allowlisted package to the personal plugin directory, updates the personal marketplace, and invokes Codex installation.
- `scripts/build_plugin_assets.py`: creates deterministic PNG presentation assets using the standard library.
- `tests/test_plugin_launcher.py`: launcher unit and command-contract tests.
- `tests/test_plugin_package.py`: manifest, skills, assets, and installer tests.
- `.codex-plugin/plugin.json`: plugin identity and install-surface metadata.
- `skills/{run,doctor,audit}/SKILL.md`: focused Codex workflows.
- `assets/icon.png`, `assets/logo.png`: generated plugin presentation assets.
- `README.md`: plugin installation, invocation, platform limits, and judge test path.
- `.github/workflows/tests.yml`: include plugin tests and validation in the existing Linux matrix.

---

### Task 1: Launcher Preflight and External State

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/gate_plugin.py`
- Create: `tests/test_plugin_launcher.py`

**Interfaces:**
- Produces: `PluginError`, `DoctorReport`, `resolve_repo()`, `ensure_supported_platform()`, `default_state_home()`, `allocate_state_dir()`, and `doctor()`.
- Consumes: `git`, `codex`, the active absolute Python interpreter, and optional `GATE_STATE_HOME`/`XDG_STATE_HOME` environment values.

- [ ] **Step 1: Write failing launcher preflight tests**

Add tests that import `scripts.gate_plugin` and assert:

```python
def test_native_windows_fails_closed():
    with pytest.raises(PluginError, match="WSL 2"):
        ensure_supported_platform(os_name="nt")


def test_resolve_repo_uses_git_root(tmp_path):
    repo = tmp_path / "repo with spaces"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    nested = repo / "src"
    nested.mkdir()
    assert resolve_repo(None, cwd=nested) == repo.resolve()


def test_allocate_state_dir_is_external_and_unique(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    state_home = tmp_path / "state"
    first = allocate_state_dir(repo, state_home=state_home)
    second = allocate_state_dir(repo, state_home=state_home)
    assert first != second
    assert not first.is_relative_to(repo)
    assert first.is_dir() and second.is_dir()


def test_state_home_inside_repo_is_rejected(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(PluginError, match="outside"):
        allocate_state_dir(repo, state_home=repo / ".gate")
```

Use injected command execution in doctor tests to assert that Python 3.10+, `codex --version`, `codex exec --help`, `codex exec resume --help`, `codex login status`, and isolated pytest import are checked. Assert a custom verifier skips the pytest import check.

- [ ] **Step 2: Run the preflight tests and verify RED**

Run: `python -m pytest tests/test_plugin_launcher.py -q`

Expected: collection fails because `scripts.gate_plugin` does not exist.

- [ ] **Step 3: Implement the minimum preflight API**

Implement these signatures:

```python
class PluginError(RuntimeError):
    pass


@dataclass(frozen=True)
class DoctorReport:
    repo: Path
    python: Path
    python_version: str
    codex: Path
    codex_version: str
    verifier: str
    state_home: Path


def ensure_supported_platform(*, os_name: str | None = None) -> None:
    current = os.name if os_name is None else os_name
    if current == "nt":
        raise PluginError("Gate requires Linux, macOS, or WSL 2; native Windows is unsupported.")
```

Also implement `resolve_repo(repo: Path | None, *, cwd: Path | None = None) -> Path`, `default_state_home(*, environ: Mapping[str, str] | None = None) -> Path`, `allocate_state_dir(repo: Path, *, state_home: Path | None = None) -> Path`, and `doctor(repo: Path, *, verifier: str | None = None, command_runner: CommandRunner = run_capture) -> DoctorReport`. `resolve_repo` must use `git -C <candidate> rev-parse --show-toplevel`. `doctor` must validate exact installed capabilities from command output, not merely executable presence. All subprocess calls use argv lists and `shell=False`.

- [ ] **Step 4: Run launcher preflight tests and verify GREEN**

Run: `python -m pytest tests/test_plugin_launcher.py -q`

Expected: all Task 1 tests pass.

- [ ] **Step 5: Commit Task 1**

```bash
git add scripts/__init__.py scripts/gate_plugin.py tests/test_plugin_launcher.py
git commit -m "feat: add Gate plugin preflight"
```

---

### Task 2: Run and Audit Commands

**Files:**
- Modify: `scripts/gate_plugin.py`
- Modify: `tests/test_plugin_launcher.py`

**Interfaces:**
- Consumes: Task 1 `doctor()` and `allocate_state_dir()`.
- Produces: `build_gate_argv()`, `run_gate()`, `build_audit_argv()`, `run_audit()`, `build_parser()`, and `main()`.

- [ ] **Step 1: Write failing command tests**

Add tests asserting:

```python
def test_run_parser_requires_exactly_one_task_source():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["run"])
    with pytest.raises(SystemExit):
        parser.parse_args(["run", "--task-text", "fix", "--task-file", "task.md"])


def test_gate_argv_uses_absolute_python_plugin_core_and_state_dir(tmp_path):
    argv = build_gate_argv(
        repo=tmp_path / "repo", task_path=tmp_path / "task.txt",
        state_dir=tmp_path / "state", verifier=None, timeout=60, max_retries=2,
    )
    assert Path(argv[0]).is_absolute()
    assert Path(argv[1]) == PLUGIN_ROOT / "gate.py"
    assert argv[argv.index("--state-dir") + 1] == str(tmp_path / "state")


def test_custom_verifier_is_forwarded_as_one_argument(tmp_path):
    argv = build_gate_argv(
        repo=tmp_path / "repo", task_path=tmp_path / "task.txt",
        state_dir=tmp_path / "state", verifier="python -m pytest checks -q",
        timeout=60, max_retries=2,
    )
    assert argv[argv.index("--verifier") + 1] == "python -m pytest checks -q"


def test_audit_uses_bundled_verify_chain(tmp_path):
    argv = build_audit_argv(tmp_path / "audit.jsonl")
    assert Path(argv[0]).is_absolute()
    assert Path(argv[1]) == PLUGIN_ROOT / "verify_chain.py"
```

Add equivalent concrete tests for external task-text copying, explicit task-file resolution, Gate and audit exit-code passthrough, and `GATE_PLUGIN_ERROR`/exit 2 behavior. Use a recording `process_runner(argv, cwd)` callable rather than invoking a child Codex process. Assert every argv element separately so paths containing spaces cannot be re-tokenized.

- [ ] **Step 2: Run command tests and verify RED**

Run: `python -m pytest tests/test_plugin_launcher.py -q`

Expected: failures report missing command functions and parser behavior.

- [ ] **Step 3: Implement command dispatch**

Implement `run_gate(args: argparse.Namespace, process_runner: ProcessRunner = run_streaming) -> int`, `build_audit_argv(log_path: Path) -> list[str]`, `run_audit(args: argparse.Namespace, process_runner: ProcessRunner = run_streaming) -> int`, `build_parser() -> argparse.ArgumentParser`, and `main(argv: Sequence[str] | None = None) -> int`. Construct Gate argv as follows:

```python
def build_gate_argv(*, repo: Path, task_path: Path, state_dir: Path,
                    verifier: str | None, timeout: float,
                    max_retries: int) -> list[str]:
    argv = [
        str(Path(sys.executable).resolve()), str(PLUGIN_ROOT / "gate.py"),
        "--repo", str(repo), "--task", str(task_path),
        "--state-dir", str(state_dir), "--log", str(state_dir / "logs"),
        "--timeout", str(timeout), "--max-retries", str(max_retries),
    ]
    if verifier is not None:
        argv.extend(["--verifier", verifier])
    return argv
```

For `--task-text`, write UTF-8 text to `<state_dir>/task.txt` and pass that path to Gate. For `--task-file`, resolve the explicit existing file. Pass `--state-dir` and `--log <state_dir>/logs` explicitly. Print `GATE_PLUGIN_STATE <path>` before launch and preserve the child exit code.

- [ ] **Step 4: Run launcher tests and the existing Gate tests**

Run: `python -m pytest tests/test_plugin_launcher.py tests/test_cli.py tests/test_verdicts.py -q`

Expected: all selected tests pass.

- [ ] **Step 5: Commit Task 2**

```bash
git add scripts/gate_plugin.py tests/test_plugin_launcher.py
git commit -m "feat: add Gate plugin run and audit commands"
```

---

### Task 3: Plugin Manifest, Skills, and Assets

**Files:**
- Create: `.codex-plugin/plugin.json`
- Create: `skills/run/SKILL.md`
- Create: `skills/doctor/SKILL.md`
- Create: `skills/audit/SKILL.md`
- Create: `scripts/build_plugin_assets.py`
- Create: `assets/icon.png`
- Create: `assets/logo.png`
- Create: `tests/test_plugin_package.py`

**Interfaces:**
- Consumes: `scripts/gate_plugin.py` subcommands.
- Produces: plugin `gate` version `0.1.0` and namespaced skills `$gate:run`, `$gate:doctor`, and `$gate:audit`.

- [ ] **Step 1: Write failing package tests**

Tests must load the manifest and skill files and assert:

```python
def test_manifest_identifies_gate_and_only_bundles_skills():
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
    assert manifest["name"] == "gate"
    assert manifest["skills"] == "./skills/"
    assert {"hooks", "mcpServers", "apps"}.isdisjoint(manifest)


@pytest.mark.parametrize("name", ["run", "doctor", "audit"])
def test_each_skill_has_frontmatter_and_launcher_command(name):
    text = (ROOT / "skills" / name / "SKILL.md").read_text()
    assert text.startswith("---\n")
    assert f"name: {name}" in text
    assert "scripts/gate_plugin.py" in text


def test_png_assets_have_expected_signature_and_dimensions():
    for name, size in (("icon.png", 128), ("logo.png", 512)):
        data = (ROOT / "assets" / name).read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II", data[16:24]) == (size, size)
```

Add concrete tests that every manifest path exists, the run skill forbids parent-agent edits and preserves the exact verdict, and the installed `plugin-creator/scripts/validate_plugin.py` exits zero against the repository root.

- [ ] **Step 2: Run package tests and verify RED**

Run: `python -m pytest tests/test_plugin_package.py -q`

Expected: failures report the missing manifest, skills, and assets.

- [ ] **Step 3: Add manifest and skill workflows**

Create a manifest with:

```json
{
  "name": "gate",
  "version": "0.1.0",
  "description": "Protected verification and retry for Codex coding tasks.",
  "author": {"name": "Yashwanth Gathuku"},
  "homepage": "https://devpost.com/software/gate-0lypv2",
  "repository": "https://github.com/YashwanthGathuku/gate",
  "license": "MIT",
  "keywords": ["codex", "verification", "testing", "security"],
  "skills": "./skills/",
  "interface": {
    "displayName": "Gate",
    "shortDescription": "Make coding agents earn completion.",
    "longDescription": "Run Codex through protected verification, exact-thread retries, and tamper-evident audit records.",
    "developerName": "Yashwanth Gathuku",
    "category": "Developer Tools",
    "capabilities": ["Read", "Write", "Execute"],
    "websiteURL": "https://devpost.com/software/gate-0lypv2",
    "brandColor": "#14B86E",
    "composerIcon": "./assets/icon.png",
    "logo": "./assets/logo.png",
    "defaultPrompt": "Run this coding task through Gate and report the exact verdict and audit root."
  }
}
```

Each skill must tell Codex to resolve the plugin root from the absolute `SKILL.md` path, run the adjacent plugin's `scripts/gate_plugin.py` with an absolute Python executable, avoid editing before `$gate:run`, and relay exact verdict/audit lines. The run skill may claim success only for child exit zero plus `FINAL VERIFIED`.

- [ ] **Step 4: Generate deterministic assets**

Implement `build_plugin_assets.py` with standard-library `struct` and `zlib`. Generate 128x128 and 512x512 RGBA PNGs with a charcoal field, a green gate outline, and a white check. Run:

`python scripts/build_plugin_assets.py`

Expected: `assets/icon.png` and `assets/logo.png` are created with the tested dimensions.

- [ ] **Step 5: Validate package and verify GREEN**

Run:

```bash
python -m pytest tests/test_plugin_package.py -q
python C:/Users/Gathu/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

Expected: package tests pass and validator prints `Plugin validation passed`.

- [ ] **Step 6: Commit Task 3**

```bash
git add .codex-plugin skills scripts/build_plugin_assets.py assets tests/test_plugin_package.py
git commit -m "feat: package Gate as a Codex plugin"
```

---

### Task 4: Safe Personal Marketplace Installer

**Files:**
- Create: `scripts/install_plugin.py`
- Modify: `tests/test_plugin_package.py`

**Interfaces:**
- Produces: `copy_plugin()`, `update_marketplace()`, and installer `main()`.
- Copies only `.codex-plugin`, `skills`, `scripts`, `assets`, `gate.py`, `gatelib`, `verify_chain.py`, `LICENSE`, and `README.md`.

- [ ] **Step 1: Write failing installer tests**

Add tests asserting:

```python
def test_copy_plugin_uses_allowlist_and_excludes_git_and_tests(tmp_path):
    source = seed_plugin_source(tmp_path / "source")
    destination = tmp_path / "home" / "plugins" / "gate"
    copy_plugin(source, destination)
    assert (destination / "gate.py").is_file()
    assert not (destination / ".git").exists()
    assert not (destination / "tests").exists()


def test_update_marketplace_preserves_unrelated_plugins(tmp_path):
    path = tmp_path / ".agents" / "plugins" / "marketplace.json"
    write_marketplace(path, plugins=[{"name": "other", "source": {"source": "local", "path": "./plugins/other"}}])
    update_marketplace(path, plugin_path=tmp_path / "plugins" / "gate")
    payload = json.loads(path.read_text())
    assert [entry["name"] for entry in payload["plugins"]] == ["other", "gate"]


def test_installer_refuses_source_without_valid_manifest(tmp_path):
    with pytest.raises(InstallError, match="plugin.json"):
        copy_plugin(tmp_path / "empty", tmp_path / "plugins" / "gate")
```

Add concrete tests for replacing Gate in place and invoking `codex plugin add gate@personal --json` as argv. Use temporary source, home, and marketplace paths. Inject the Codex process runner; never modify the real user marketplace from unit tests.

- [ ] **Step 2: Run installer tests and verify RED**

Run: `python -m pytest tests/test_plugin_package.py -q`

Expected: failures report missing installer functions.

- [ ] **Step 3: Implement safe installation**

Use this allowlist and implement `update_marketplace(path: Path, *, plugin_path: Path, marketplace_name: str = "personal") -> None` plus `main(argv: Sequence[str] | None = None, process_runner: ProcessRunner = run_process) -> int`:

```python
PACKAGE_ENTRIES = (
    ".codex-plugin", "skills", "scripts", "assets", "gate.py", "gatelib",
    "verify_chain.py", "LICENSE", "README.md",
)


def copy_plugin(source: Path, destination: Path) -> None:
    manifest = source / ".codex-plugin" / "plugin.json"
    if not manifest.is_file():
        raise InstallError(f"missing plugin.json under {source}")
    destination.mkdir(parents=True, exist_ok=True)
    for name in PACKAGE_ENTRIES:
        item = source / name
        target = destination / name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        elif item.is_file():
            shutil.copy2(item, target)
```

Write JSON atomically with a sibling temporary file and `os.replace`. Preserve unrelated marketplace keys and plugin order; replace Gate in place or append it. The entry source is `./plugins/gate`, installation is `AVAILABLE`, authentication is `ON_INSTALL`, and category is `Developer Tools`. After copying and updating, run `codex plugin add gate@personal --json` with `shell=False`.

- [ ] **Step 4: Run installer and package tests**

Run: `python -m pytest tests/test_plugin_package.py -q`

Expected: all package and installer tests pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add scripts/install_plugin.py tests/test_plugin_package.py
git commit -m "feat: add Gate personal plugin installer"
```

---

### Task 5: Documentation, CI, and Acceptance Evidence

**Files:**
- Modify: `README.md`
- Modify: `.github/workflows/tests.yml`
- Create: `docs/evidence/plugin_validation.txt`
- Create: `docs/evidence/plugin_rehearsal_console.txt`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: reproducible install/run/audit instructions and permanent acceptance output.

- [ ] **Step 1: Add documentation assertions before editing README**

Extend `tests/test_plugin_package.py` to require README sections and commands for:

```text
Codex plugin
python scripts/install_plugin.py
$gate:doctor
$gate:run
$gate:audit
Linux, macOS, or WSL 2
native Windows
```

- [ ] **Step 2: Run documentation test and verify RED**

Run: `python -m pytest tests/test_plugin_package.py -q`

Expected: README contract test fails on missing plugin instructions.

- [ ] **Step 3: Update README and CI**

Document local installation, plugin invocation, supported platforms, the fact that `$gate:run` starts a separate Gate-controlled child session, exact local uninstall command, and judge rehearsal steps. Update CI so the existing Python 3.10/3.13 job runs the full suite and the plugin validator.

- [ ] **Step 4: Run complete local verification**

Run:

```bash
python -m pytest tests -q
python C:/Users/Gathu/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
python scripts/gate_plugin.py audit docs/evidence/audit_20260720_165329.jsonl
git diff --check
```

Expected: 0 failures; plugin validation passes; audit prints `VALID: 12 records`; diff check is clean.

- [ ] **Step 5: Run packaged fake-agent rehearsal on POSIX/WSL**

From Linux, macOS, or WSL 2, use `$gate:run` or its exact launcher command against a disposable seeded fixture with the fake agent and require `FALSIFIED -> TAMPERED -> VERIFIED`. Save complete console output to `docs/evidence/plugin_rehearsal_console.txt` and plugin validator output to `docs/evidence/plugin_validation.txt`.

- [ ] **Step 6: Install the cached plugin and perform live acceptance**

Run the local installer, confirm `codex plugin list` shows Gate from the cached copy, start a new Codex task that explicitly invokes `$gate:doctor`, then perform one authenticated `$gate:run` on POSIX/WSL. Record the exact child thread, terminal verdict, audit path, and root. Native Windows rejection is acceptance evidence for native Windows, not a substitute for the supported-platform live run.

- [ ] **Step 7: Commit Task 5**

```bash
git add README.md .github/workflows/tests.yml docs/evidence tests/test_plugin_package.py
git commit -m "docs: add Gate plugin installation and evidence"
```

---

### Task 6: Final Review and Publication Readiness

**Files:**
- Review all plugin changes.
- Modify only files required by review findings.

**Interfaces:**
- Produces: a clean feature branch ready to push and merge.

- [ ] **Step 1: Review security invariants against the approved design**

Confirm line by line that plugin code does not alter protected patterns, verifier defaults, exact resume behavior, process-group cleanup, verdict mapping, or audit chaining. Confirm no target-repository setup file is written before Gate freezes the repository.

- [ ] **Step 2: Review package boundaries**

Inspect the installed copy and confirm it excludes `.git`, `.worktrees`, `.venv`, test fixtures, videos, local state, and private paths while including every runtime file referenced by the three skills.

- [ ] **Step 3: Run final verification from a clean state**

Run:

```bash
python -m pytest tests -q
python C:/Users/Gathu/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
git diff --check
git status --short
```

Expected: all tests pass, plugin validation passes, diff check is clean, and only intentional evidence changes remain.

- [ ] **Step 4: Use the finishing-a-development-branch workflow**

Review commits, report any unavailable WSL/live evidence explicitly, and present merge/push options without claiming public plugin availability before OpenAI accepts the submission.
