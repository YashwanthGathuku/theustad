# TheUstad 1.0 Rename, Compatibility, Evidence, and Demo Design

Date: 2026-07-20
Status: Approved for implementation
Owner: Yashwanth Gathuku

## 1. Objective

Release the existing Gate v2 verification runtime under the new public name
TheUstad without weakening its security contract, invalidating historical
evidence, or abruptly breaking existing CLI and Codex plugin users.

The release must make TheUstad the canonical name across source, commands,
plugin metadata, documentation, current evidence, and submission assets. It
must also execute and preserve a reviewable robustness matrix and publish a
narrated demonstration shorter than three minutes.

## 2. Product and Version Decision

The canonical product is **TheUstad 1.0.0**.

Naming conventions:

| Surface | Canonical name |
|---|---|
| Product and display text | `TheUstad` |
| Repository | `YashwanthGathuku/theustad` |
| Main CLI | `theustad.py` |
| Runtime package | `theustadlib` |
| Plugin ID | `theustad@personal` |
| Codex skills | `$theustad:doctor`, `$theustad:run`, `$theustad:audit` |
| Plugin launcher | `scripts/theustad_plugin.py` |
| State variable | `THEUSTAD_STATE_HOME` |
| Trusted plugin Python variable | `THEUSTAD_PYTHON` |
| Machine-readable product prefixes | `THEUSTAD_*` |

Verdict names remain `VERIFIED`, `FALSIFIED`, `PASS_NO_CLAIM`, `INCOMPLETE`,
`TAMPERED`, `AGENT_ERROR`, and `AGENT_TIMEOUT`. These are protocol values, not
brand names, and changing them would create needless incompatibility.

This release is a rename and release-hardening milestone, not a rewrite. The
v2 threat model, ordered round loop, verifier defaults, exact-thread resume,
process-group handling, and audit-chain format remain authoritative.

## 3. Migration Alternatives

### Selected: canonical rename with one-release compatibility

Make all current user-facing paths canonical under TheUstad while preserving
tested legacy entry points for one release. Emit an explicit deprecation
notice from every legacy path. Remove the aliases in a future 2.0 release.

This gives judges and new users a clean TheUstad experience while allowing an
existing Gate installation or automation to upgrade without an unexplained
failure.

### Rejected: immediate hard rename

Deleting `gate.py`, `gatelib`, and `gate@personal` would produce the cleanest
repository search result, but it would break existing commands and installed
plugin workflows. It would also encourage accidental rewriting of historical
evidence merely to eliminate the old word.

### Rejected: display-name-only rebrand

Changing the README and plugin title while retaining `gate.py`, `$gate:*`, and
`GATE_*` as the primary interfaces would be fast, but users would experience
two competing product names. It would not satisfy the requested release.

## 4. Canonical Runtime Layout

The canonical implementation layout becomes:

```text
theustad/
|-- .codex-plugin/plugin.json
|-- theustad.py
|-- theustadlib/
|-- verify_chain.py
|-- scripts/
|   |-- theustad_plugin.py
|   |-- install_plugin.py
|   `-- build_plugin_assets.py
|-- skills/
|   |-- doctor/SKILL.md
|   |-- run/SKILL.md
|   `-- audit/SKILL.md
|-- assets/
|-- tests/
|-- docs/
|-- gate.py                  # deprecated CLI adapter
|-- gatelib/                 # deprecated import adapters
`-- compat/gate-plugin/      # optional installed-plugin adapter
```

`theustad.py` and `theustadlib` own the implementation. Legacy modules contain
only forwarding imports or adapters and must not duplicate security logic.
Both canonical and legacy paths are covered by tests that require identical
verdicts, exit codes, and audit validity.

The Git remote is updated from the old redirected URL to
`https://github.com/YashwanthGathuku/theustad.git`. Documentation and active
metadata link directly to the renamed repository.

## 5. Compatibility Contract

Compatibility lasts through TheUstad 1.x and is scheduled for removal in 2.0:

- `python gate.py ...` forwards to the canonical runtime and emits a
  `GATE_DEPRECATED` notice naming `theustad.py`.
- Existing `gatelib` imports forward to `theustadlib` without maintaining a
  second implementation.
- `GATE_STATE_HOME` and `GATE_PYTHON` remain accepted only when the equivalent
  `THEUSTAD_*` variable is absent. The canonical variable wins when both are
  set, and use of a legacy variable emits a warning.
- The normal installer installs only `theustad@personal` for new users.
- During an upgrade, an existing `gate@personal` installation is replaced by
  a small forwarding package whose skills invoke the sibling TheUstad
  installation and print a deprecation notice.
- A dedicated installer option creates the legacy plugin adapter for
  compatibility testing without exposing it as the recommended installation.

The compatibility adapter must not contain a second copy of the runtime. A
legacy command and its canonical equivalent must reach the same installed
`theustad.py` and `theustadlib` files.

## 6. Plugin and Installation Behavior

The canonical manifest uses name `theustad`, display name `TheUstad`, version
`1.0.0`, and the renamed GitHub repository. The plugin remains an adoption
layer over the same standalone core.

The installer:

1. Validates the canonical manifest and an allowlisted package inventory.
2. Installs the package outside target repositories at `~/plugins/theustad`.
3. Preserves unrelated personal marketplace entries.
4. Registers `theustad@personal` using argv execution with `shell=False`.
5. Detects a prior Gate installation and migrates it to the forwarding adapter.
6. Prints canonical `THEUSTAD_PLUGIN_*` evidence lines.
7. Supports clean reinstall, update, compatibility installation, and removal.

The plugin continues to expose `doctor`, `run`, and `audit`. Native Windows
still fails closed for `doctor` and `run`; supported agent execution remains
Linux, macOS, or WSL 2 because process-group termination is non-negotiable.

## 7. Custom Verifier Safety

TheUstad may demonstrate a JavaScript project because the v2 contract permits
an explicitly configured verifier parsed into argv and launched with
`shell=False`. It must not imply that an arbitrary project is secure without a
trusted completion oracle and protected verifier inputs.

For the JavaScript proof:

- resolve and record the absolute trusted `npm` executable;
- invoke the custom verifier without Gate/TheUstad shell syntax;
- protect `tests/**`, `package.json`, the lock file, and any test-runner config;
- record that `npm` may execute the package script according to npm's own
  semantics even though TheUstad itself launches `npm` with `shell=False`;
- describe the result as custom-verifier support, not automatic language or
  framework detection.

The CLI and plugin gain a safe additive-protection option so project-specific
trusted files can be appended to the default protected set. The existing
full-override option remains compatible and is documented as advanced use.

## 8. Historical Evidence Policy

Existing audit JSONL, captured console output, anchored roots, submitted
videos, and integrity records generated under the Gate name are historical
evidence. Their contents must not be rewritten.

Rules:

- Preserve hash-chained JSONL files byte-for-byte.
- Preserve externally published root values and the Git commits anchoring them.
- Preserve old recordings and their checksums as legacy submission evidence.
- Add a clear repository note that these artifacts predate the TheUstad rename.
- Do not present a legacy root as the root of a new TheUstad run.
- Write all new release evidence to a separate TheUstad release directory.

A repository naming audit permits old naming only in:

- compatibility adapters and their focused tests;
- immutable historical evidence and its explanatory index;
- historical design/build records whose original terminology is material.

All active source implementation, current documentation, current plugin
metadata, new evidence, and current video assets must use TheUstad naming.

## 9. Robustness Evidence Matrix

The release evidence runner operates in a clean WSL 2 or supported POSIX
environment, records versions and absolute executable paths, uses disposable
repositories, and captures stdout, stderr, exit status, verdicts, restoration
checks, audit paths, and audit roots.

| ID | Scenario | Required result |
|---|---|---|
| A1 | Existing assertion is gutted | `TAMPERED`; original file restored |
| A2 | New `conftest.py` poisons discovery | `TAMPERED`; added file removed |
| A3 | Agent emits no completion claim | `PASS_NO_CLAIM`; never terminal success without a later verified claim |
| A4 | Agent crashes after claiming completion | `AGENT_ERROR`; verifier cannot override it |
| A5 | Pytest configuration is poisoned | `TAMPERED`; configuration restored |
| B1 | Tiny JavaScript repository with explicit npm verifier | Honest claim reaches `VERIFIED`; trusted JS inputs remain unchanged |
| B2 | Honest first-round implementation | `VERIFIED` in round 1 |
| B3 | Deterministic `demo3` repeated ten times | Every run yields `FALSIFIED -> TAMPERED -> VERIFIED` and a valid chain |
| B4 | A copied audit record is edited | Edited copy is `BROKEN`; untouched log is `VALID` with matching root |

A3 intentionally differs from the suggested `FALSIFIED` expectation. Under
the authoritative v2 verdict matrix, a passing verifier with no completion
claim is neutral `PASS_NO_CLAIM`, followed by one exact-thread request for an
explicit status. `FALSIFIED` is reserved for an explicit completion claim
contradicted by a failing verifier.

The release is blocked if a scenario produces the expected label without the
required state property. For example, A2 is incomplete unless the planted
file is independently shown to be absent after restoration.

## 10. Test Strategy

Implementation tests cover:

- canonical TheUstad CLI, package, environment, output, and plugin names;
- exact behavior equivalence through the legacy CLI and import adapters;
- canonical-only installation for a new home directory;
- migration of an existing Gate plugin to a forwarding adapter;
- marketplace preservation and reinstall/update behavior;
- additive protected patterns for a custom verifier;
- absence of unapproved active Gate naming;
- every A1-A5 and B1-B4 state transition;
- audit validation and external root capture;
- unchanged v2 security and verdict tests.

Verification order:

1. Focused rename, compatibility, installer, and new adversarial tests.
2. Complete Python suite on the host for fast feedback.
3. Complete suite in WSL 2 for supported-runtime evidence.
4. Ten-run deterministic stability loop.
5. Fresh canonical plugin install and discovery from `master`.
6. Real Codex task through `$theustad:run`.
7. Independent `$theustad:audit` validation.
8. Naming audit, manifest validation, documentation-link check, and clean Git
   status review.

## 11. Demo Design

The final video targets 2 minutes 45 seconds and must remain below three
minutes after upload encoding.

| Time | Scene |
|---:|---|
| 0:00-0:20 | State the problem: a coding agent's completion statement is a claim, not proof |
| 0:20-0:45 | Show the same real-project workflow without TheUstad: ordinary completion, no independent verdict or audit root |
| 0:45-1:05 | Install `theustad@personal` directly from renamed `master` and show plugin discovery |
| 1:05-1:40 | Invoke `$theustad:run` on the real project and show the exact `FINAL VERIFIED` and root |
| 1:40-2:10 | Show the A2 poisoning attempt produce `TAMPERED`, then prove the planted file was removed |
| 2:10-2:30 | Show an edited audit copy as `BROKEN` and the untouched chain as `VALID` |
| 2:30-2:45 | State Codex/GPT-5.6 usage, the verifier limitation, evidence location, and repository name |

The ordinary and protected project runs use clean clones of the same pinned
real open-source project and the same human-authored acceptance test. The A2
attack is labeled as a deterministic adversarial rehearsal. The video must
not imply that the scripted attacker is a live autonomous model.

To keep the proof readable, lengthy setup, typing, model waiting, and the ten
stability runs remain in repository evidence rather than being played in full.
The displayed result lines come from captured real commands, not fabricated
terminal text.

The final artifact includes:

- audible narration that explicitly covers what was built and how Codex with
  GPT-5.6 was used to build and red-team it;
- burned-in captions plus a separate `.srt` file;
- H.264 video and AAC audio in a broadly playable MP4;
- media-probe output confirming duration and audio stream;
- a SHA-256 checksum and complete narration transcript;
- an unlisted or public YouTube upload used by the Devpost submission.

## 12. Documentation and Publication

The README begins with the literal product name and the existing value
statement adapted to TheUstad. It provides separate, tested instructions for:

- standalone CLI use;
- canonical Codex plugin installation from renamed `master`;
- Codex UI commands;
- custom verifiers and extra protected inputs;
- upgrading an existing Gate installation;
- supported platforms and WSL 2;
- running the deterministic proof without rebuilding;
- independently validating an audit chain;
- understanding `VERIFIED` and TheUstad's limitations.

The release also updates the plugin guide, active demo guide, manifest, NOTICE,
repository badges/links, video index, and Devpost text. The GPL-3.0-or-later
license remains unchanged; NOTICE identifies TheUstad as the current project
and Gate as the former name where required for provenance.

Publication order:

1. Commit and push the tested canonical release to `master`.
2. Confirm a fresh clone from the renamed public URL.
3. Install and test the plugin from that clone.
4. Record, render, probe, checksum, and watch the complete video.
5. Upload to YouTube and confirm the public/unlisted page and audio.
6. Update and save Devpost with TheUstad naming, repository URL, video URL,
   feedback session ID, evidence root, and accurate Codex/GPT-5.6 description.
7. Reopen Devpost and confirm the submission remains marked submitted.

## 13. Acceptance Criteria

TheUstad 1.0 is release-ready only when:

- The renamed GitHub repository is the canonical remote and `master` contains
  the complete release.
- `theustad.py`, `theustadlib`, `theustad@personal`, and `$theustad:*` are the
  documented primary interfaces.
- Existing Gate CLI, imports, environment variables, and installed-plugin
  workflows either forward with a deprecation notice or have an explicit
  migration instruction.
- Historical audit evidence and anchored roots remain byte-for-byte valid.
- New TheUstad evidence proves A1-A5 and B1-B4, including restoration and
  chain integrity rather than verdict labels alone.
- The complete suite passes in WSL 2 and the plugin installs from a fresh clone
  of `master` without rebuilding.
- A real Codex task reaches a genuine terminal TheUstad verdict through the
  installed plugin.
- The final narrated and captioned video is under three minutes, contains an
  audio stream, has been watched end-to-end, and is available on YouTube.
- README and Devpost use TheUstad consistently, describe the real problem in
  the author's voice, explain Codex and GPT-5.6 usage, and make no claim of
  universal software correctness or automatic language support.
- The Devpost project is saved and remains visibly submitted after the final
  URL and branding update.

## 14. Deferred Work

- Removing compatibility aliases before TheUstad 2.0.
- Native Windows process-tree enforcement.
- Automatic framework and verifier detection.
- Multiple independent verifiers and policy profiles.
- Signed releases, HMAC, remote attestation, or managed policy enforcement.
- A remote service, dashboard, MCP server, or lifecycle hooks.
