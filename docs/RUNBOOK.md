# GATE v2 — Runbook (Fri Jul 17 → Tue Jul 21, 2026)

## ⚠️ DO FIRST — TODAY, FRIDAY JULY 17

- [ ] **Codex credits request form — closes 12:00 PM PT TODAY.**
      Miss it and Prompt 8 runs on your own plan/key instead. Build
      Week codes expire Jul 21, 5 PM PT.
- [ ] Devpost registration confirmed, category **Developer Tools**.

## Environment (30 minutes)

```bash
npm i -g @openai/codex          # or brew install --cask codex
codex login                     # ChatGPT plan or API key
python3 --version               # ≥ 3.10
pip install pytest
mkdir gate && cd gate
# from the v1 zip, copy IN: demo_repo/  task.md  verify_chain.py
# from this kit, copy IN:   docs/SPEC.md  docs/PROMPTS.md
git init && git add -A && git commit -m "workspace: spec + fixture + oracle"
cd demo_repo && git init && git add -A && git commit -m "seed" && cd ..
```
v1 `gate.py`/`fake_codex.py` stay OUTSIDE this folder (private diff
oracle only).

## Day plan

| Day | Work | Exit condition (evidence, not feelings) |
|---|---|---|
| **Fri 17** | Credits form. Setup. Prompts 0–2 | schema_samples.jsonl exists; events+claims tests green (pasted) |
| **Sat 18** | Prompts 3–6 | full `pytest gate/tests -q` green |
| **Sun 19** | Prompt 7 e2e; then Prompt 8 live fire | demo3 verdict sequence FALSIFIED→TAMPERED→VERIFIED in audit log; one live codex run completed; `/feedback` ID saved |
| **Mon 20** | Record video; README; Devpost draft; anchor root hash | video file exists; repo public; draft complete |
| **Tue 21** | Buffer + submit by **12:00 PM PT** (deadline 5 PM PT) | Devpost shows "submitted" |

Falling behind? Cut in this order: HMAC option → `crash` scenario →
extra adversarial claim cases. **Never cut:** freezer, demo3 e2e,
the video.

## The demo video (~2 minutes, one take, rehearsed)

Terminal font large. Script:

1. **Setup (10s):** "Coding agents claim 'done.' Gate checks whether
   that's true — in a process the agent doesn't control." Show
   `task.md` (ticket #4127).
2. **Beat 1 — false claim (30s):** run gate (rehearsal, demo3).
   Agent fixes parser, claims "ready to merge." Gate runs the FULL
   suite itself → `2 failed` → **FALSIFIED**, evidence injected back.
3. **Beat 2 — cheating (30s):** agent deletes the failing test file,
   claims "all tests pass" — and the tests genuinely are green now.
   Gate's frozen manifest catches it → **TAMPERED**, file restored,
   diff logged. "It can't grade its own homework — and can't eat it
   either."
4. **Beat 3 — honest (25s):** proper fix → **VERIFIED**. Root hash
   banner. `python verify_chain.py audit_*.jsonl` → VALID. Flip one
   verdict in a copy → `BROKEN at seq N`.
5. **Live coda (15s):** cut to the real `codex exec` run from
   Prompt 8, landing on its verdict. "Same gate, real agent."
6. **Close (10s):** "Claim lexicon compiled from my open-source
   evidence-gate skill. Built through Codex — session ID in the
   submission."

## Devpost submission checklist

- [ ] Name: decide in ≤5 min, functional beats clever ("Gate" +
      one word if taken). No brainstorm session.
- [ ] Category: Developer Tools.
- [ ] `/feedback` session ID from the Prompt 0–7 build session.
- [ ] Public repo; README has install + test instructions
      (`pip install pytest`, `pytest gate/tests -q`, rehearsal
      command, live command) — required for dev-tools entries.
- [ ] Honesty block in README: verified-in-repo vs assumed
      (post-Prompt-0 this list should be nearly empty).
- [ ] Audit root hash pasted into submission text AND in a git
      commit message (external anchor).
- [ ] Video uploaded; plays without sound making sense too
      (captions on beats).
- [ ] Provenance line: "Core built in Codex from a written spec
      (docs/SPEC.md); seeded fixture and chain-format oracle
      provided as inputs; v1 prototype used only as a private
      diff reference."

## Judging map (write these sentences, roughly, in the submission)

- **Codex/GPT-5.6 use:** built *through* Codex (session ID) and built
  *for* Codex — gate wraps `codex exec` and resumes sessions by
  thread id with falsification evidence.
- **Implementation:** six modules, own pytest suite incl. e2e; audit
  chain byte-verified by an independent script.
- **Impact:** false completion claims and test-tampering are the two
  failure modes every agent user hits; gate converts both into
  logged, falsifiable verdicts.
- **Novelty:** not "run tests after the agent" — the verifier's
  inputs are themselves defended (frozen manifest), and evidence
  re-enters the same session. Anti-reward-hacking as a harness, not
  a paper.

## Risk table

| Risk | Mitigation |
|---|---|
| JSONL schema differs from adapters | Prompt 0 captures real samples first; adapters tested against them |
| Sandbox blocks agent writes | flag verified in Prompt 0; demo_repo is its own git repo |
| Credits denied/late | rehearsal mode needs zero credits; Prompt 8 can run on your own plan |
| Live codex fixes everything round 1 | that's a VERIFIED story — say "gate confirms honest work"; rehearsal carries the falsification beats |
| Time overrun | cut order above; scope wall is SPEC §6 |
| New idea arrives mid-build | it goes in `docs/PARKING.md`, not in the repo. That is the whole discipline. |
