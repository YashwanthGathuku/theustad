# TheUstad 1.0 — Codex Prompt Sequence

Use this sequence with `docs/SPEC.md` and `docs/RUNBOOK.md`. Prompts
0–7 belong in one Codex session using GPT-5.6. Prompt 8 runs from a
separate terminal because TheUstad will itself spawn `codex exec`.

Rules for the build session:

1. Read the referenced SPEC section before editing.
2. Do not add features from SPEC §6's out-of-scope list.
3. Every prompt ends with an acceptance command. Paste its real output.
4. If Codex says “done” without evidence, reply: `Falsified until
   proven. Run the acceptance command and paste the output.`
5. After each accepted prompt, commit with `prompt N: ... green`.
6. After Prompt 7, run `/feedback` and save the session ID.

## Workspace before Prompt 0

```text
theustad/
├── START_HERE.md
├── CODEX_HANDOFF.md
├── docs/
│   ├── SPEC.md
│   ├── PROMPTS.md
│   └── RUNBOOK.md
├── verify_chain.py
├── demo_repo/
├── task.md
└── .git/
```

The legacy implementation and v1 `fake_codex.py` must remain outside this
workspace. They are private review references, not implementation
inputs.

---

## Prompt 0 — Reality check and contract update

```text
Read docs/SPEC.md, docs/PROMPTS.md, and docs/RUNBOOK.md fully. Do not
write implementation code yet.

We are building TheUstad 1.0 for OpenAI Build Week using GPT-5.6. First
resolve every item in SPEC §7 with command evidence.

1. Run and paste:
   codex --version
   codex exec --help
   codex exec resume --help
   python --version

2. Report the exact JSON-output flag, sandbox/workspace-write syntax,
   resume-by-thread-id syntax, and Git-repository behavior for this
   installed Codex version.

3. Tell me one separate shell command to capture a real ping stream to
   docs/schema_samples.jsonl. I will run it outside this active Codex
   session and tell you when the file exists. Then read the file and
   list every event type plus the exact field path containing agent
   message text and thread id.

4. Record the selected GPT-5.6 model and Codex version in
   docs/BUILD_EVIDENCE.md.

5. In a disposable temporary test directory, prove that the absolute
   trusted Python interpreter with isolated mode can run genuine pytest
   without importing a planted local pytest.py. Do not modify the real
   demo_repo for this check.

6. Update only the UNVERIFIED command forms in SPEC §4.5 and §7 if the
   installed CLI differs. Show the diff.

Do not claim completion until the command outputs, schema sample,
BUILD_EVIDENCE entry, isolated-pytest evidence, and SPEC diff are shown.
```

Acceptance: `docs/schema_samples.jsonl` and
`docs/BUILD_EVIDENCE.md` exist; CLI assumptions are resolved; no
implementation module exists yet.

---

## Prompt 1 — Package scaffold and JSONL events

```text
Per SPEC §3 and §4.1, create the theustadlib package scaffold and implement
theustadlib/events.py completely: parse_line, extract_agent_text,
extract_thread_id, and describe.

Write tests/test_events.py covering all documented schemas, string and
content-block messages, malformed lines, events without agent text,
thread/session ids, and the real events in docs/schema_samples.jsonl.

Acceptance: run `python -m pytest tests/test_events.py -q` and paste the
complete output. Show `git diff --stat`.
```

---

## Prompt 2 — Completion claims

```text
Per SPEC §4.2, implement theustadlib/claims.py and tests/test_claims.py.
Use only the final agent message supplied by the orchestrator. Do not
treat standalone “working” or progress language as completion.

Include every required case from SPEC §4.2 verbatim, plus at least five
mixed-sentence adversarial cases. Specifically test:
  “I am working on it.” -> no claim
  “Parser tests pass, but the task is not complete.” -> no claim
  “I am not done. The previous error said tests pass.” -> no claim
  “Fixed the crash; ready to merge.” -> claim

Acceptance: run `python -m pytest tests/test_claims.py -q` and paste
the output. Show `git diff --stat`.
```

---

## Prompt 3 — Protected-input freezer

```text
Per SPEC §4.3, implement theustadlib/freezer.py. The snapshot must live
under an explicit TheUstad-owned state_dir outside the target repository;
refuse a state_dir inside the repo. Handle files without following
protected repository symlinks.

Write tests/test_freezer.py covering:
  - modify and delete an existing protected test;
  - add a protected conftest.py;
  - add pytest.py and pytest/__main__.py;
  - add sitecustomize.py;
  - replace a protected file with a symlink/type change;
  - edit app/ without a tamper result;
  - refuse state_dir inside repo;
  - restore returns the manifest to clean and removes planted paths.

Acceptance: run `python -m pytest tests/test_freezer.py -q` and paste
the output. Show the created snapshot path from one test and prove it
is outside the target repo.
```

---

## Prompt 4 — Audit chain

```text
Per SPEC §4.6, implement theustadlib/chain.py while keeping byte
compatibility with the existing verify_chain.py oracle. Do not add
HMAC or signing; external root anchoring is the v2 design.

Write tests/test_chain.py: create a five-record chain and verify it via
verify_chain.py; flip a middle record and require BROKEN with nonzero
exit; confirm a second run creates a different timestamped log rather
than erasing the first.

Acceptance: run `python -m pytest tests/test_chain.py -q` and paste the
output.
```

---

## Prompt 5 — Trusted verifier and agent session

```text
Per SPEC §4.4 and §4.5, implement theustadlib/verifier.py and
theustadlib/session.py using the CLI forms verified in Prompt 0.

Verifier requirements:
  - argv list and shell=False;
  - absolute sys.executable with -I for default pytest;
  - custom command parsed by shlex.split without shell operators;
  - merged evidence tail;
  - verifier timeout returns 124.

Session requirements on POSIX/WSL:
  - stream JSONL without losing non-JSON evidence;
  - capture first thread id and last agent message;
  - expose exit code;
  - enforce timeout even when the child is silent;
  - start a process group and terminate background descendants after
    normal exit or timeout.

Write tests/test_verifier.py proving a planted local pytest.py cannot
fake the trusted default verifier. Write tests/test_session.py with an
exit-0 stub, exit-2 stub, silent-timeout stub, and a stub that launches
a background child; prove the child is terminated.

Acceptance: run
`python -m pytest tests/test_verifier.py tests/test_session.py -q`
and paste the complete output.
```

---

## Prompt 6 — Orchestrator and verdict semantics

```text
Per SPEC §4.7, implement theustad.py. Follow the round order exactly:
agent process group stopped -> tamper check/restore -> agent exit
check -> classify final message -> pre-verifier tamper check -> trusted
verifier -> post-verifier tamper check -> verdict.

TAMPERED overrides claims and verifier output. AGENT_ERROR and
AGENT_TIMEOUT cannot become stale-green success. PASS_NO_CLAIM is
neutral, does not exit 0, and may resume once asking for an explicit
completion status. Only VERIFIED exits 0.

Write tests/test_verdicts.py with every verdict and precedence rule.
Include a race test in which a protected file changes between the
pre-verifier and post-verifier checks and must become TAMPERED.

Acceptance: run `python -m pytest tests -q` and paste the full output.
Then show `python theustad.py --help`.
```

---

## Prompt 7 — Adversarial rehearsal and end-to-end proof

```text
Per SPEC §4.8 and §4.9, implement fake_codex.py with demo3, naive2,
and crash scenarios. The patches and pytest commands must really run;
only the agent reasoning is scripted.

Create the seeded reset snapshot from the untouched demo_repo before
the first rehearsal mutation. Add tests/test_e2e_rehearsal.py that:
  - resets the fixture;
  - runs demo3 through TheUstad;
  - asserts FALSIFIED -> TAMPERED -> VERIFIED in order;
  - verifies the deleted invoice test was restored;
  - asserts final exit 0;
  - validates the audit chain;
  - runs the crash scenario and requires AGENT_ERROR/nonzero.

Update README.md with supported platforms, installation, rehearsal,
live command, exact threat-model limits, and a clear label that demo3
is a deterministic adversarial rehearsal.

Acceptance: paste one complete manual demo3 run, then run
`python -m pytest tests -q` and paste the full output. Show the final
README diff.
```

After acceptance:

```text
/feedback
```

Save the session ID in `docs/BUILD_EVIDENCE.md`, commit, and tag:

```bash
git tag core-built-in-codex
```

---

## Prompt 8 — Live Codex fire test

Run this from a separate terminal, outside the Prompt 0–7 build chat:

```bash
cd theustad
python theustad.py --repo demo_repo --task task.md
```

Accept either real outcome:

- Codex makes the narrow fix first: `FALSIFIED`, evidence resume,
  proper fix, `VERIFIED`.
- Codex finds the complete fix immediately: `VERIFIED` in round 1.

If JSONL adapters miss a real shape, paste the raw event into the
original build session, update `events.py` and its tests, rerun the
full suite, and commit the fix. Record the rehearsal and live run for
the demo video.
