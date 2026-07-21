# TheUstad 1.0 — Build and Submission Runbook

Schedule: Friday July 17 through Tuesday July 21, 2026.

This runbook is operational. `docs/SPEC.md` is the product contract,
and `docs/PROMPTS.md` is the implementation sequence. If prose in this
runbook conflicts with the spec, the spec wins.

## 0. Do these before coding

- Submit the Codex credits request form before **12:00 PM PT on Friday,
  July 17**. This is the only nonrecoverable task in the plan.
- Confirm Devpost registration and select **Developer Tools**.
- Use GPT-5.6 for the Codex build session and preserve evidence of the
  selected model and session.
- On Windows, use WSL 2. Native Windows is not supported by this build.

If the credits form is already closed, continue with the same build on
the available ChatGPT plan or API credits. Do not change product scope.

## 1. Know what is in this starter

The starter intentionally contains only:

```text
theustad/
├── START_HERE.md
├── CODEX_HANDOFF.md
├── docs/
│   ├── SPEC.md
│   ├── PROMPTS.md
│   └── RUNBOOK.md
├── demo_repo/
├── task.md
└── verify_chain.py
```

The legacy implementation files, old `fake_codex.py`, and temporary red-team
attack scripts are intentionally excluded. They are evidence and private diff
references, not inputs to the compliant Codex implementation.

## 2. Prepare the workspace

From a Linux, macOS, or WSL 2 shell:

```bash
cd theustad
python3 --version
git --version
codex --version
```

If Codex is not installed, install and authenticate it using one of the
supported methods for the machine, for example:

```bash
npm install -g @openai/codex
codex login
```

Create a local Python environment and install the development dependency:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip pytest
```

Initialize the build repository first, then give the guinea-pig repo its
own baseline history:

```bash
git init
git add -A
git commit -m "workspace: v2 spec, prompts, runbook, and fixture"
cd demo_repo
git init
git add -A
git commit -m "seed: broken duration fixture"
cd ..
```

Confirm the fixture starts broken. The expected result is **1 failed,
10 passed**:

```bash
python -m pytest demo_repo/tests -q
```

That command intentionally exits nonzero. Do not repair the fixture
manually; TheUstad's rehearsal agents need it.

## 3. Start the compliant Codex build

1. Open this folder in Codex on desktop or start Codex from this folder.
2. Select GPT-5.6. For a CLI supporting the standard model flag, use:

   ```bash
   codex -m gpt-5.6
   ```

3. Paste the contents of `CODEX_HANDOFF.md` as the first message.
4. Let Codex execute **Prompt 0 only**, then inspect its command evidence.
5. Run the separate schema-capture command Prompt 0 gives you in another
   terminal. Return to the same session when the sample exists.
6. Do not start Prompt 1 until all Prompt 0 acceptance conditions pass.

This file-and-prompt handoff is the chat transfer. Do not paste the full
planning conversation; it contains stale alternatives and would weaken
the single source of truth.

## 4. Execute Prompts 1–7 in one session

Use `docs/PROMPTS.md` in order. For every prompt:

1. Paste only that prompt.
2. Require the complete acceptance-command output.
3. Inspect the diff and unexpected files.
4. If the acceptance test is green, commit it:

   ```bash
   git add -A
   git commit -m "prompt N: acceptance green"
   ```

5. If Codex reports success without evidence, answer:

   ```text
   Falsified until proven. Run the stated acceptance command and paste
   the complete output.
   ```

Keep Prompts 0–7 in the same session so the required `/feedback` record
covers the core build. Prompt 8 is deliberately launched from a second
terminal because TheUstad itself starts `codex exec`.

## 5. Day-by-day exit conditions

| Day | Work | Do not stop until |
|---|---|---|
| Fri Jul 17 | Form, setup, Prompts 0–2 | schema sample and build evidence exist; event and claim tests pass |
| Sat Jul 18 | Prompts 3–6 | the complete TheUstad unit suite passes |
| Sun Jul 19 | Prompt 7 and Prompt 8 | rehearsal records `FALSIFIED → TAMPERED → VERIFIED`; one live Codex run finishes |
| Mon Jul 20 | README, video, public repo, Devpost draft | video plays; repo instructions work from clean setup; audit root is externally anchored |
| Tue Jul 21 | Buffer and submission | Devpost shows submitted before the deadline |

If behind, cut in this order: optional crash rehearsal, extra claim
phrases, presentation polish. Never cut the protected-input freezer,
module-shadowing defense, three-beat adversarial rehearsal, live Codex
run, `/feedback` session ID, or video.

## 6. Required evidence folder

Keep these artifacts before recording:

- `docs/schema_samples.jsonl` from the installed Codex CLI.
- `docs/BUILD_EVIDENCE.md` with Codex version and GPT-5.6 selection.
- Complete TheUstad test output.
- A rehearsal audit containing `FALSIFIED`, `TAMPERED`, and `VERIFIED`.
- One live `codex exec` audit.
- The `/feedback` session ID from the Prompt 0–7 build session.
- Final audit root hash in both a pushed Git commit message and Devpost
  text. That external anchor is what makes later log rewriting visible.

Do not publish secrets, API keys, raw environment dumps, or private
paths in these artifacts.

## 7. Two-minute demo

Use a large terminal font and captions. Rehearse with the deterministic
fake agent; label it plainly as an adversarial rehearsal.

1. **Setup — 10 seconds.** “Coding agents claim done. TheUstad checks the
   claim using protected evidence.” Show `task.md`.
2. **False claim — 30 seconds.** The agent makes the obvious parser fix
   and claims completion. TheUstad runs the full suite and records
   `FALSIFIED`, then returns the failing invoice evidence to the session.
3. **Test deletion — 30 seconds.** The agent deletes the failing test
   and gets green tests. TheUstad detects the protected-input change,
   records `TAMPERED`, restores the baseline, and returns the diff.
   “It cannot grade its own homework—or eat it.”
4. **Honest fix — 25 seconds.** The agent repairs the compatibility
   behavior; TheUstad records `VERIFIED`.
5. **Audit — 15 seconds.** Verify the chain, show the anchored root, then
   verify a deliberately edited copy and show the break. Never edit the
   original evidence log.
6. **Live coda — 15 seconds.** Show the real Codex run from Prompt 8.
7. **Close — 10 seconds.** State that the core was built through Codex
   from the written spec and identify the build session evidence.

## 8. Devpost checklist

- [ ] Credits form submitted, or the fallback funding path recorded.
- [ ] Devpost project registered under Developer Tools.
- [ ] Public repository contains install, test, rehearsal, and live-run
      instructions that were retested from a clean environment.
- [ ] GPT-5.6/Codex build provenance and `/feedback` session ID included.
- [ ] Honesty block distinguishes verified behavior, assumptions, and
      out-of-scope threats.
- [ ] Audit root hash appears in a pushed commit and submission text.
- [ ] Video has captions and makes sense without audio.
- [ ] Submission uses no fabricated scores or unsupported comparison
      claims.
- [ ] Project is actually submitted, not merely saved as a draft.

Suggested provenance sentence:

> Core built in Codex from `docs/SPEC.md`; the seeded fixture and
> independent chain-format checker were supplied as inputs. The v1
> prototype and red-team scripts were used only as private review
> references and were not placed in the build workspace.

## 9. Scope discipline

Until TheUstad is submitted, new product ideas go in a parking note rather
than implementation. In particular, DeployGraph/Salesforce validation
is a future verifier pack for TheUstad, not part of this build. The unlock
condition is a completed TheUstad submission.
