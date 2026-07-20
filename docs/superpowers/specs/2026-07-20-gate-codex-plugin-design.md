# Gate Codex Plugin Design

Date: 2026-07-20
Status: Proposed for implementation
Owner: Yashwanth Gathuku

## 1. Objective

Distribute Gate as an installable Codex plugin so a user can invoke Gate from
the project they are already working in without copying Gate source files into
that project or manually assembling the `gate.py` command.

The plugin is an installation and invocation layer. The existing Gate v2 core
remains the authority for session control, protected snapshots, verification,
verdicts, retries, and audit records.

## 2. Product Decision

Use one repository and one installation:

- The Gate repository becomes the plugin package by adding the required
  `.codex-plugin/plugin.json` manifest.
- The installed plugin contains the existing `gate.py`, `gatelib/`, and
  `verify_chain.py` core outside the target repository.
- Three bundled skills provide the user workflows: `run`, `doctor`, and
  `audit`.
- A deterministic Python launcher translates those workflows into argv-based
  Gate commands.
- No MCP server and no lifecycle hooks are included in the first release.

This is preferable to a separate Gate CLI installation because it gives users
one install while keeping the runtime outside the project being modified. It is
preferable to an MCP server because Gate is already a local process
orchestrator and does not need a persistent service or remote API.

## 3. Alternatives Rejected

### Skill only

A skill containing instructions but no bundled runtime would be easy to build,
but users would still need to clone or install Gate separately. Instructions
alone also cannot produce a trusted verdict.

### Plugin with lifecycle hooks

Hooks can make suggestions or run checks during a Codex lifecycle, but they do
not replace Gate's wrapper semantics: start a fresh controlled session, capture
the exact thread ID, terminate the process group, verify, and resume that same
thread. Plugin hooks also require a separate trust review and can be disabled.
They therefore cannot be Gate's security boundary.

### Plugin with an MCP server

An MCP server could expose `gate.run` and `gate.audit` tools, but it introduces
protocol, process-lifetime, timeout, approval, and packaging work without
improving the v2 verifier. It remains a future option if Gate later needs a
structured API, centralized policy, or remote verifier service.

## 4. Package Layout

```text
gate/
|-- .codex-plugin/
|   `-- plugin.json
|-- skills/
|   |-- run/
|   |   `-- SKILL.md
|   |-- doctor/
|   |   `-- SKILL.md
|   `-- audit/
|       `-- SKILL.md
|-- scripts/
|   `-- gate_plugin.py
|-- assets/
|   |-- icon.png
|   `-- logo.png
|-- gate.py
|-- gatelib/
|-- verify_chain.py
|-- tests/
`-- docs/
```

The manifest identifies the plugin as `gate`, points at `./skills/`, and
contains marketplace metadata. It does not declare hooks, MCP servers, or an
app connector.

The repository root is the plugin root. Codex installs a copy into its plugin
cache, so the bundled Gate runtime is not placed in the target repository.

## 5. User Workflows

### `$gate:doctor`

Run a read-only preflight for the current project:

1. Resolve the current Git repository root.
2. Require Linux, macOS, or WSL 2. Fail closed on native Windows.
3. Require Python 3.10 or newer and resolve its absolute executable path.
4. Require the Codex CLI and inspect the installed version and required exec
   options.
5. Check that the selected Python environment can import pytest when the
   default verifier will be used.
6. Report the target repository, interpreter, verifier, and external state
   root without changing project files.

### `$gate:run`

Run Gate against the current project:

1. Use the current Git root as `--repo` unless the user explicitly supplies a
   different repository.
2. Use task text supplied with the request or an explicitly named task file,
   preserving that distinction when calling the launcher.
3. Run doctor checks before starting Codex.
4. Create a fresh state directory under
   `${GATE_STATE_HOME:-~/.local/state/gate}/<repo-id>/<run-id>/`.
5. Invoke the bundled `gate.py` with an absolute Python executable and an argv
   list, never through a shell command string.
6. Stream Gate output without reclassifying or summarizing away verdict,
   audit-path, or root-hash lines.
7. Return Gate's exit status and show the exact audit path and root.

The skill must not edit the target repository before launching Gate. Once Gate
starts, only the child `codex exec` session performs the requested coding task.

For the first release, pytest is the default verifier. A different verifier is
accepted only when the user supplies the command explicitly; the plugin does
not guess a project's completion oracle.

### `$gate:audit`

Verify an existing audit log using the bundled independent
`verify_chain.py`:

1. Require an explicit audit-log path or use the most recent log only after
   displaying the resolved path.
2. Run the verifier with an absolute Python executable and argv list.
3. Return `VALID` or `BROKEN`, the record count, and the root.
4. Remind the user that validity is meaningful against an externally anchored
   root; do not claim signing or remote attestation.

## 6. Launcher Contract

`scripts/gate_plugin.py` is a thin deterministic adapter with these commands:

```text
gate_plugin.py doctor [--repo PATH] [--verifier COMMAND]
gate_plugin.py run [--repo PATH]
                   (--task-text TEXT | --task-file PATH)
                   [--verifier COMMAND] [--timeout SECONDS]
                   [--max-retries COUNT]
gate_plugin.py audit LOG_PATH
```

The launcher:

- resolves the plugin root from its own file location;
- resolves the target repository before constructing state paths;
- uses `subprocess` argv lists with `shell=False`;
- launches the bundled core with `Path(sys.executable).resolve()`;
- creates state directories outside the target repository with private
  permissions where the platform supports them;
- preserves Gate's stdout, stderr, and exit code;
- never changes protected patterns, verdict semantics, timeout handling, or
  verifier defaults;
- rejects native Windows instead of silently running with weaker process-tree
  behavior.

The launcher may improve preflight errors and defaults, but it may not catch a
nonzero Gate verdict and present it as success.

## 7. Security Boundaries

The plugin preserves the existing v2 threat model:

- The installed core and run state are outside the target repository.
- Gate freezes protected inputs before starting the child coding agent.
- The child agent receives workspace-write access to the target repository,
  not authority over the external snapshot or plugin cache.
- Gate continues to use exact thread-ID resume, process-group termination,
  pre-verifier and post-verifier manifest checks, isolated trusted Python,
  `shell=False`, explicit timeouts, final-message claim classification, and
  the existing verdict matrix.
- The audit root still requires an external anchor.

The plugin does not claim to secure an already-running Codex conversation. A
user must invoke `$gate:run`, which starts a new Gate-controlled child session.
The parent conversation is a launcher and result viewer, not the agent whose
completion claim is being graded.

The plugin also does not expand Gate's platform support or defend against a
hostile operating-system user, same-user process outside the Codex sandbox,
kernel compromise, or a weak verifier.

## 8. Failure Behavior

- Unsupported platform: exit before any child agent starts and provide WSL 2
  guidance on Windows.
- Missing Codex CLI or authentication: exit with the exact failed preflight.
- Missing pytest for the default verifier: exit and name the absolute Python
  environment that needs pytest.
- Non-Git target: exit before Gate starts because the default Codex invocation
  requires a trusted repository.
- State path inside the target repository: reject it, even if explicitly
  configured.
- Gate verdict other than `VERIFIED`: preserve Gate's nonzero exit status.
- Audit verification failure: return nonzero and do not print a success label.

## 9. Testing Strategy

### Launcher unit tests

- Plugin-root and repository-root resolution, including paths with spaces.
- State directories are outside the target repository and unique per run.
- Native Windows rejection and WSL/Linux/macOS acceptance.
- Python and Codex preflight failures are explicit.
- Commands use argv with `shell=False`.
- Task text and task-file handling are unambiguous.
- Gate and audit exit codes pass through unchanged.

### Plugin package tests

- Validate `.codex-plugin/plugin.json` with the current plugin validator.
- Validate all skill frontmatter and referenced paths.
- Assert the manifest contains no hooks, MCP server, or app connector.
- Install through a personal marketplace and confirm Codex loads all three
  namespaced skills from the cached plugin copy.

### End-to-end tests

- Run the bundled launcher against a disposable copy of the seeded fixture and
  require `FALSIFIED -> TAMPERED -> VERIFIED` with the fake agent.
- Verify the resulting audit with the bundled audit workflow.
- Confirm the plugin runtime and state paths are outside the target repository.
- Run the existing Gate test suite unchanged on Python 3.10 and 3.13.

A live Codex acceptance run through the installed plugin is required before
public submission. Build, unit, or fake-agent evidence alone is insufficient.

## 10. Distribution

Development proceeds in three stages:

1. Add the plugin files to this repository and validate them locally.
2. Add a personal marketplace entry outside the repository, install the cached
   copy in Codex, and complete the local and live acceptance tests.
3. Add public metadata and submit the same package through the Codex plugin
   submission process.

The personal marketplace configuration is local machine state and must not be
committed. The repository may later expose a repository marketplace catalog if
that improves testing or team distribution.

## 11. Acceptance Criteria

The plugin MVP is complete only when all of the following are true:

- One plugin installation exposes `doctor`, `run`, and `audit` skills.
- No Gate source or trusted state is copied into the target repository.
- A Gate-controlled run starts from the current project with task text and no
  manually assembled command.
- Existing Gate security and verdict tests remain green.
- Plugin launcher and packaging tests are green.
- The installed cached plugin completes the fake-agent rehearsal.
- A real Codex run launched through the installed plugin reaches and reports a
  genuine terminal Gate verdict.
- The emitted audit validates independently and its root is shown for external
  anchoring.
- Documentation states the WSL 2 requirement on Windows and does not claim
  automatic protection for ordinary, non-Gate Codex chats.

## 12. Deferred Work

- Lifecycle hooks that only remind users to invoke Gate.
- An MCP tool API for centralized or remote Gate execution.
- Native Windows process-tree support.
- Project templates or committed Gate configuration.
- Multiple verifier profiles and non-Python auto-detection.
- Signed releases, HMAC, remote attestation, or managed policy enforcement.
