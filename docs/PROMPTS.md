# GATE v2 — Codex Prompt Sequence

## How to run this session (read first)

1. **One session for the core build.** Prompts 0–7 go into a single
   `codex` session in the `gate/` workspace. The submission requires a
   `/feedback` session ID for the thread where most core functionality
   was built — run `/feedback` at the end of Prompt 7 and save the ID
   immediately. Prompt 8 (live fire) runs in a *separate* terminal
   because gate itself will be spawning `codex exec`.
2. **SPEC.md is on disk.** Every prompt says "per docs/SPEC.md §N" —
   don't re-paste contracts; make Codex read the file.
3. **Evidence, every prompt.** Each prompt ends by demanding a command
   run + pasted output. If Codex answers "done" without output, reply
   exactly: `Falsified until proven. Run the acceptance command and
   paste the output.` (You are running gate's philosophy on the tool
   building gate. Say that in the Devpost writeup.)
4. **Scope defense.** If Codex proposes extras (dashboards, plugins,
   more scenarios), reply: `Out of scope per SPEC §6. Continue.`
5. **Commit after every green prompt:**
   `git add -A && git commit -m "prompt N: <module> green"`.
   The commit trail is your build provenance.

## Workspace before Prompt 0

```
gate/
├── docs/SPEC.md            ← from this kit
├── docs/PROMPTS.md         ← this file
├── verify_chain.py         ← v1 oracle (chain format must stay compatible)
├── demo_repo/              ← v1 seeded fixture (parser/invoice/tests)
├── task.md                 ← ticket #4127
└── .git/                   ← git init; initial commit
```
The v1 `gate.py` and `fake_codex.py` stay OUT of this workspace.
Codex builds fresh from spec; the old zip is your private diff oracle.

---

## Prompt 0 — recon (resolves SPEC §7, no code yet)

```
Read docs/SPEC.md fully. Do not write implementation code yet.

Task 1: Verify the four UNVERIFIED items in SPEC §7 against the codex
CLI installed on this machine. Run:
  codex --version
  codex exec --help
  codex exec resume --help 2>&1 | head -40
Report the exact flag names for JSON output and sandbox mode, and the
exact resume-by-id syntax.

Task 2: From a SEPARATE plain shell (tell me the command; I will run
it and paste results), we will capture:
  codex exec --json "reply with exactly: ping" > docs/schema_samples.jsonl
Then read docs/schema_samples.jsonl and list every distinct event
type and the exact field path where agent message text lives.

Task 3: Update SPEC §3.5 defaults and §3.1 adapter notes in
docs/SPEC.md to match reality. Show me the diff.

Do not claim completion without pasting the command outputs.
```

**Acceptance:** schema_samples.jsonl exists; SPEC diff shown; you know
the real flags. Commit.

---

## Prompt 1 — scaffold + events.py

```
Per docs/SPEC.md §2 and §3.1: create the package scaffold (gatelib/
with empty modules, gate/tests/ with __init__.py) and implement
gatelib/events.py completely: parse_line, extract_agent_text
(shapes A/B/C plus content-block lists), extract_thread_id,
describe. Then write gate/tests/test_events.py covering: all three
shapes, the recorded events in docs/schema_samples.jsonl (load the
file in the test), content-block lists, malformed JSON lines, and
events with no agent text.

Acceptance: run `python -m pytest gate/tests/test_events.py -q` and
paste the output. Do not claim completion without it.
```

---

## Prompt 2 — claims.py

```
Per docs/SPEC.md §3.2: implement gatelib/claims.py (LEXICON,
find_claims with sentence splitting, question suppression, negation
window ≤ 8 tokens). Write gate/tests/test_claims.py containing the
seven-row table from §3.2 verbatim as parametrized cases, plus five
additional adversarial cases you design (mixed sentences where one
sentence claims and another negates, claim word inside a quoted
error message, etc.). 

Acceptance: `python -m pytest gate/tests/test_claims.py -q` — paste
output.
```

---

## Prompt 3 — freezer.py

```
Per docs/SPEC.md §3.3: implement gatelib/freezer.py (freeze, check,
restore; snapshot lives in a tempfile.mkdtemp owned by gate; default
protected patterns per spec). Write gate/tests/test_freezer.py: 
modify a test file → detected as modified; delete one → deleted;
plant a new conftest.py → added; edits under app/ → ignored;
restore → check clean; restore removes planted files.

Acceptance: `python -m pytest gate/tests/test_freezer.py -q` — paste
output.
```

---

## Prompt 4 — chain.py (+ HMAC in verify_chain.py)

```
Per docs/SPEC.md §3.6: implement gatelib/chain.py. The serialization
must be byte-compatible with the existing verify_chain.py in the repo
root — treat that file as the oracle and DO NOT change its hashing
logic; only add an optional --hmac-key argument to it (HMAC-SHA256
over the same payload). Write gate/tests/test_chain.py: build a
5-record chain, verify VALID via subprocess call to verify_chain.py;
flip a middle record → BROKEN nonzero exit; HMAC chain verifies with
the right key and BREAKS with a wrong key.

Acceptance: `python -m pytest gate/tests/test_chain.py -q` — paste
output.
```

---

## Prompt 5 — verifier.py + session.py

```
Per docs/SPEC.md §3.4 and §3.5: implement gatelib/verifier.py and
gatelib/session.py using the flags verified in Prompt 0. session.py
must: stream events live (bufsize=1), yield parsed events, capture
thread_id (first seen), expose exit_code, resume by explicit thread
id with --last fallback + warning. Unit-test session.py against a
stub script that prints three JSONL lines and exits 0, and another
that exits 2 (exit_code surfaced). Test verifier timeout with
`sleep 5` and timeout=1 → exit 124.

Acceptance: `python -m pytest gate/tests/test_session.py
gate/tests/test_verifier.py -q` — paste output.
```

---

## Prompt 6 — gate.py orchestrator

```
Per docs/SPEC.md §3.7: implement gate.py — CLI, round loop in the
exact order (tamper check FIRST, then agent exit, then claim×verifier
matrix), injection messages per spec, live-feed printing (cyan agent,
yellow gate, dim events, red/green verdicts), timestamped audit log
path, final root-hash banner with the external-anchor instruction,
exit code 0 iff VERIFIED or PASS_NO_CLAIM.

Write gate/tests/test_verdicts.py driving the verdict matrix through
stubbed session/freezer/verifier objects: all six verdicts reachable,
TAMPERED beats everything, AGENT_ERROR beats claims.

Acceptance: `python -m pytest gate/tests -q` (full suite) — paste
output.
```

---

## Prompt 7 — fake_codex.py + end-to-end

```
Per docs/SPEC.md §3.8: implement fake_codex.py with scenarios demo3,
naive2, crash. Patches must really hit disk and pytest must really
run inside it (only the LLM is scripted). Then write
gate/tests/test_e2e_rehearsal.py: reset demo_repo to seed (restore
app/parser.py and app/invoice.py from demo_repo/.seed — create that
snapshot dir first from current seeded state), run gate.py as a
subprocess with --cmd "python fake_codex.py --scenario demo3"
--max-retries 3, assert the verdict sequence FALSIFIED, TAMPERED,
VERIFIED appears in order in the audit log, final exit 0, and
verify_chain.py reports VALID.

Acceptance: paste (1) the full live output of one manual demo3 run,
(2) `python -m pytest gate/tests -q` full-suite output. Both green
or it is not done.
```

**After acceptance:** run `/feedback`, save the session ID. Commit.
Tag: `git tag core-built-in-codex`.

---

## Prompt 8 — live fire (separate terminal, uses credits)

```
(plain shell, not inside the build session)
cd gate && python gate.py --repo demo_repo --task task.md
```
Real codex takes ticket #4127. Expected: it may fix only the parser
(FALSIFIED → resume with evidence → proper fix → VERIFIED), or fix
both immediately (VERIFIED round 1 — also a good story: gate
*confirms* honest work). If events don't parse: feed the raw lines
back into the build session — `events.py adapters missed this shape:
<paste>. Fix and re-run tests.`

Record BOTH a demo3 rehearsal run and the live run for the video.
