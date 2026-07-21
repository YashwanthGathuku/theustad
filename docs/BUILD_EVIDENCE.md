# TheUstad 1.0 Build Evidence

The dated command/output sections below predate the product rename and remain
verbatim historical evidence. Their Gate-named paths, protocol samples, roots,
and outcomes are indexed in `docs/evidence/LEGACY_GATE_EVIDENCE.md`; new
TheUstad evidence is recorded separately under `docs/evidence/theustad-1.0/`.

## Prompt 0 environment

- Date: 2026-07-17
- Selected build model: GPT-5.6
- Python: 3.13.5
- Host shell: PowerShell on native Windows
- Supported runtime note: no WSL distribution is installed, so this host does
  not currently satisfy SPEC section 1's WSL 2 requirement for running Gate.
- Follow-up on 2026-07-20: Ubuntu 24.04 under WSL 2 was installed and the live
  standalone CLI and installed-plugin runs were completed there. See
  `docs/evidence/real_project_demo/README.md`; the original Prompt 0 observation
  above is retained as historical evidence.
- Codex Desktop package: `OpenAI.Codex_26.715.2305.0_x64__2p2nqsd0c76g0`
- Codex CLI executable:
  `C:\Users\Gathu\AppData\Local\OpenAI\Codex\bin\5dee10576ec7a5b8\codex.exe`
- Codex CLI version: `codex-cli 0.145.0-alpha.18`
- Authentication status: initially not logged in; authenticated with ChatGPT
  before the successful external schema and non-Git probes on 2026-07-18.

## Required CLI diagnostics

```text
> codex --version
codex-cli 0.145.0-alpha.18
[exit 0]

> codex exec --help
Run Codex non-interactively

Usage: codex exec [OPTIONS] [PROMPT]
       codex exec [OPTIONS] <COMMAND> [ARGS]

Commands:
  resume  Resume a previous session by id or pick the most recent with --last
  review  Run a code review against the current repository
  help    Print this message or the help of the given subcommand(s)

Arguments:
  [PROMPT]
          Initial instructions for the agent. If not provided as an argument (or if `-` is used),
          instructions are read from stdin. If stdin is piped and a prompt is also provided, stdin
          is appended as a `<stdin>` block

Options:
  -c, --config <key=value>
          Override a configuration value that would otherwise be loaded from `~/.codex/config.toml`.
          Use a dotted path (`foo.bar.baz`) to override nested values. The `value` portion is parsed
          as TOML. If it fails to parse as TOML, the raw string is used as a literal.

          Examples: - `-c model="o3"` - `-c 'sandbox_permissions=["disk-full-read-access"]'` - `-c
          shell_environment_policy.inherit=all`

      --enable <FEATURE>
          Enable a feature (repeatable). Equivalent to `-c features.<name>=true`

      --disable <FEATURE>
          Disable a feature (repeatable). Equivalent to `-c features.<name>=false`

      --strict-config
          Error out when config.toml contains fields that are not recognized by this version of
          Codex

  -i, --image <FILE>...
          Optional image(s) to attach to the initial prompt

  -m, --model <MODEL>
          Model the agent should use

      --oss
          Use open-source provider

      --local-provider <OSS_PROVIDER>
          Specify which local provider to use (lmstudio or ollama). If not specified with --oss,
          will use config default or show selection

  -p, --profile <CONFIG_PROFILE_V2>
          Layer $CODEX_HOME/<name>.config.toml on top of the base user config

  -s, --sandbox <SANDBOX_MODE>
          Select the sandbox policy to use when executing model-generated shell commands

          [possible values: read-only, workspace-write, danger-full-access]

      --dangerously-bypass-approvals-and-sandbox
          Skip all confirmation prompts and execute commands without sandboxing. EXTREMELY
          DANGEROUS. Intended solely for running in environments that are externally sandboxed

      --dangerously-bypass-hook-trust
          Run enabled hooks without requiring persisted hook trust for this invocation. DANGEROUS.
          Intended only for automation that already vets hook sources

  -C, --cd <DIR>
          Tell the agent to use the specified directory as its working root

      --add-dir <DIR>
          Additional directories that should be writable alongside the primary workspace

      --skip-git-repo-check
          Allow running Codex outside a Git repository

      --ephemeral
          Run without persisting session files to disk

      --ignore-user-config
          Do not load `$CODEX_HOME/config.toml`; auth still uses `CODEX_HOME`

      --ignore-rules
          Do not load user or project execpolicy `.rules` files

      --output-schema <FILE>
          Path to a JSON Schema file describing the model's final response shape

      --color <COLOR>
          Specifies color settings for use in the output

          [default: auto]
          [possible values: always, never, auto]

      --json
          Print events to stdout as JSONL

  -o, --output-last-message <FILE>
          Specifies file where the last message from the agent should be written

  -h, --help
          Print help (see a summary with '-h')

  -V, --version
          Print version
[exit 0]

> codex exec resume --help
Resume a previous session by id or pick the most recent with --last

Usage: codex exec resume [OPTIONS] [SESSION_ID] [PROMPT]

Arguments:
  [SESSION_ID]
          Conversation/session id (UUID) or thread name. UUIDs take precedence if it parses. If
          omitted, use --last to pick the most recent recorded session

  [PROMPT]
          Prompt to send after resuming the session. If `-` is used, read from stdin

Options:
  -c, --config <key=value>
          Override a configuration value that would otherwise be loaded from `~/.codex/config.toml`.
          Use a dotted path (`foo.bar.baz`) to override nested values. The `value` portion is parsed
          as TOML. If it fails to parse as TOML, the raw string is used as a literal.

          Examples: - `-c model="o3"` - `-c 'sandbox_permissions=["disk-full-read-access"]'` - `-c
          shell_environment_policy.inherit=all`

      --last
          Resume the most recent recorded session (newest) without specifying an id

      --all
          Show all sessions (disables cwd filtering)

      --enable <FEATURE>
          Enable a feature (repeatable). Equivalent to `-c features.<name>=true`

      --disable <FEATURE>
          Disable a feature (repeatable). Equivalent to `-c features.<name>=false`

  -i, --image <FILE>
          Optional image(s) to attach to the prompt sent after resuming

      --strict-config
          Error out when config.toml contains fields that are not recognized by this version of
          Codex

  -m, --model <MODEL>
          Model the agent should use

      --dangerously-bypass-approvals-and-sandbox
          Skip all confirmation prompts and execute commands without sandboxing. EXTREMELY
          DANGEROUS. Intended solely for running in environments that are externally sandboxed

      --dangerously-bypass-hook-trust
          Run enabled hooks without requiring persisted hook trust for this invocation. DANGEROUS.
          Intended only for automation that already vets hook sources

      --skip-git-repo-check
          Allow running Codex outside a Git repository

      --ephemeral
          Run without persisting session files to disk

      --ignore-user-config
          Do not load `$CODEX_HOME/config.toml`; auth still uses `CODEX_HOME`

      --ignore-rules
          Do not load user or project execpolicy `.rules` files

      --output-schema <FILE>
          Path to a JSON Schema file describing the model's final response shape

      --json
          Print events to stdout as JSONL

  -o, --output-last-message <FILE>
          Specifies file where the last message from the agent should be written

  -h, --help
          Print help (see a summary with '-h')
[exit 0]

> python --version
Python 3.13.5
[exit 0]

> codex login status
Not logged in
[exit 1]
```

PowerShell resolution evidence:

```text
Name        : codex.exe
CommandType : Application
Source      : C:\Program Files\WindowsApps\OpenAI.Codex_26.715.2305.0_x64__2p2nqsd0c76g0\app\resources\codex.exe
Path        : C:\Program Files\WindowsApps\OpenAI.Codex_26.715.2305.0_x64__2p2nqsd0c76g0\app\resources\codex.exe
```

Resolved command forms:

```text
JSON output:              --json
Sandbox option:           -s, --sandbox <SANDBOX_MODE>
Workspace-write value:    workspace-write
Initial execution:        codex exec --json --sandbox workspace-write <task>
Exact thread-id resume:   codex exec resume --json <thread_id> <message>
Non-Git override:         --skip-git-repo-check
```

The default non-Git rejection and the override behavior were both confirmed
after authentication, as recorded below.

## Non-Git diagnostic

The disposable directory was confirmed to be outside a Git work tree:

```text
> git rev-parse --is-inside-work-tree
fatal: not a git repository (or any of the parent directories): .git
[exit 128]
```

The initial probes from the active runner were blocked before the CLI started:

```text
> codex exec --json "Reply with exactly: GATE_NON_GIT_PING"
Access is denied.

> codex exec --json --skip-git-repo-check "Reply with exactly: GATE_NON_GIT_PING"
Access is denied.
```

After authentication, the external non-Git probes produced this combined
output verbatim:

```text
{"type":"thread.started","thread_id":"019f7562-861c-7d80-bcae-43b48c8e8498"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"error","message":"Skill descriptions were shortened to fit the 2% skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest."}}
{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"GATE_NON_GIT_PING"}}
{"type":"turn.completed","usage":{"input_tokens":19582,"cached_input_tokens":11008,"cache_write_input_tokens":0,"output_tokens":11,"reasoning_output_tokens":0}}

Reading additional input from stdin...

Reading additional input from stdin...
Not inside a trusted directory and --skip-git-repo-check was not specified.
```

The explicit error confirms that default `codex exec` rejects the disposable
non-Git directory. The completed JSONL turn confirms that adding
`--skip-git-repo-check` permits execution there.

## Isolated pytest shadowing proof

Disposable directory:

```text
C:\Users\Gathu\AppData\Local\Temp\gate-prompt0-isolated-pytest-20260717
```

Planted local `pytest.py`:

```python
raise RuntimeError("PLANTED LOCAL PYTEST.PY WAS IMPORTED")
```

Genuine fixture test:

```python
def test_genuine_pytest_runs():
    assert True
```

Command and output:

```text
> C:\Users\Gathu\AppData\Local\Programs\Python\Python313\python.exe -I -c "import pytest; print(pytest.__file__)"
C:\Users\Gathu\AppData\Local\Programs\Python\Python313\Lib\site-packages\pytest\__init__.py

> C:\Users\Gathu\AppData\Local\Programs\Python\Python313\python.exe -I -m pytest -q
.                                                                        [100%]
1 passed in 0.45s
C:\Users\Gathu\AppData\Local\Programs\Python\Python313\Lib\site-packages\requests\__init__.py:113: RequestsDependencyWarning: urllib3 (2.6.3) or chardet (7.1.0)/charset_normalizer (3.4.4) doesn't match a supported version!
  warnings.warn(
C:\Users\Gathu\AppData\Local\Programs\Python\Python313\Lib\site-packages\pytest_asyncio\plugin.py:207: PytestDeprecationWarning: The configuration option "asyncio_default_fixture_loop_scope" is unset.
The event loop scope for asynchronous fixtures will default to the fixture caching scope. Future versions of pytest-asyncio will default the loop scope for asynchronous fixtures to function scope. Set the default fixture loop scope explicitly in order to avoid unexpected behavior in the future. Valid fixture loop scopes are: "function", "class", "module", "package", "session"

  warnings.warn(PytestDeprecationWarning(_DEFAULT_FIXTURE_LOOP_SCOPE_UNSET))
[exit 0]
```

The imported pytest package came from `site-packages`, not the planted local
module. The run also emitted unrelated `RequestsDependencyWarning` and
`PytestDeprecationWarning` warnings from installed third-party plugins.

## Schema capture

The first external attempt started `codex login`, timed out, and did not create
the file. After authentication, the separate external ping created
`docs/schema_samples.jsonl` with this content:

```jsonl
{"type":"thread.started","thread_id":"019f7562-4c64-7712-aec5-1bea8cdd37c4"}
{"type":"turn.started"}
{"type":"item.completed","item":{"id":"item_0","type":"error","message":"Skill descriptions were shortened to fit the 2% skills context budget. Codex can still see every skill, but some descriptions are shorter. Disable unused skills or plugins to leave more room for the rest."}}
{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"GATE_SCHEMA_PING"}}
{"type":"turn.completed","usage":{"input_tokens":19566,"cached_input_tokens":11008,"cache_write_input_tokens":0,"output_tokens":9,"reasoning_output_tokens":0}}
```

Observed schema inventory:

| Event type | Observed item subtype | Agent text path | Thread id path |
|---|---|---|---|
| `thread.started` | none | none | `$.thread_id` |
| `turn.started` | none | none | none |
| `item.completed` | `error` | none | none |
| `item.completed` | `agent_message` | `$.item.text` | none |
| `turn.completed` | none | none | none |

Unique event types: `thread.started`, `turn.started`, `item.completed`, and
`turn.completed`.

## Prompt 7 adversarial rehearsal

- Build session ID: `019f708d-eb32-72d0-a58d-fdd5ffcff511`
- Feedback completed in Codex Desktop.
- Feedback/session ID: `019f708d-eb32-72d0-a58d-fdd5ffcff511`.
- Seeded demo repository commit: `5e87582` (`seed: broken duration fixture`).
- Manual `demo3` verdicts: `FALSIFIED -> TAMPERED -> VERIFIED`.
- Manual audit root:
  `550bf5d0f2cebcdcc59996d64eccb0afbb41ff08791af1ed57fe319917f93fc9`.
- Independent chain verification: `VALID: 12 records` with the same root.

The end-to-end rehearsal found that isolated Python ignores the
`PYTHONDONTWRITEBYTECODE` environment variable. The original default verifier
therefore created `tests/__pycache__`, and Gate correctly classified that
protected-path mutation as `TAMPERED`. The trusted verifier command now uses
`-I -B -m pytest -q`: isolation still defeats local module shadowing, while
`-B` prevents the verifier itself from mutating protected test inputs.

## Prompt 8 live Codex fire test

- Date: 2026-07-19.
- Command: `python gate.py --repo demo_repo --task task.md`.
- Codex CLI: `codex-cli 0.145.0-alpha.18`, authenticated with ChatGPT.
- Live Codex thread ID: `019f78cf-2302-7670-a725-6c89a41699c8`.
- Verdicts: `INCOMPLETE -> TAMPERED -> VERIFIED`.
- Final Gate exit code: `0`.
- Audit log:
  `C:\Users\Gathu\AppData\Local\Temp\gate-v2-state-ovtf7_dn\logs\audit_20260719_051748.jsonl`.
- Audit root:
  `0faeacc75ff81ba953000d91fa94d74be195e12b2c42063ca9e9ed26019be8aa`.
- Independent chain verification: `VALID: 12 records` with the same root.
- Independent final verifier: `11 passed in 0.13s` with absolute Python,
  isolated mode, and bytecode disabled.

The native-Windows run produced a stricter path than Prompt 8's two nominal
outcomes. Round 1 could not start a sandboxed shell and accurately reported
`INCOMPLETE`. In round 2, Codex made the complete production fix and its own
test run passed all 11 tests, but that run added bytecode under protected
`tests/**`; Gate recorded `TAMPERED` and restored the baseline. Gate resumed
the exact same thread, Codex reran with `-B`, and round 3 was `VERIFIED`.

The first launch also exposed a console-boundary bug: valid UTF-8 JSONL
contained a character that strict Windows CP-1252 could not encode. Gate now
backslash-escapes only characters unsupported by the active output stream,
with a focused CP-1252 regression test. The live retry required prepending the
runnable standalone `codex-resources` directory to terminal `PATH`; otherwise
Windows selected the packaged sandbox helper and rejected its launch with OS
error 5. Gate still invoked Codex with `--sandbox workspace-write`; no sandbox
bypass flag was used.
