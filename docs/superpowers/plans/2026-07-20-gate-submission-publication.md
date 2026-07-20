# Gate Submission Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish Gate's problem-led README, public live demo, and matching Devpost submission from a verified `master` branch.

**Architecture:** Keep `gate.py` and `gatelib/` as the single enforcement core. The standalone CLI runs that core directly; the Codex plugin installs an allowlisted copy and delegates to the same `gate.py`, preserving its protected verification, exact-thread retries, process-group termination, and audit-chain behavior.

**Tech Stack:** Python 3.10+, pytest, Codex CLI/plugin skills, PowerShell, WSL 2, YouTube Studio, Devpost MCP, GitHub Actions.

## Global Constraints

- Public YouTube visibility is `Public` and audience is `not made for kids`.
- The README remains ASCII and does not claim universal correctness.
- The five public claims use the exact primary sources from the approved design.
- Gate's current license presentation is `GPL-3.0-or-later`; current-facing attribution copy does not discuss the previous license.
- The recorded counts remain 51 passed without Gate and 50 passed with the plugin.
- Audit root: `5241d2d1e9ea87699c52333d7b8c16db8b6bbda961e9921c831992cb178c186b`.
- Video SHA-256: `AC7240A101F72531E3CA69D6B601B5839C91318C1DC3D403660D229C23D26076`.
- Native Windows `doctor` and `run` remain fail-closed; successful coding runs use Linux, macOS, or WSL 2.

---

### Task 1: Publish the problem-led README

**Files:**
- Modify: `README.md`
- Modify: `tests/test_plugin_package.py`

**Interfaces:**
- Consumes: checked-in demo evidence, GPL manifest, plugin commands.
- Produces: public installation and problem narrative used by GitHub and Devpost.

- [ ] **Step 1: Add README contract assertions**

Add assertions that require the problem-led headline, all five source URLs,
the without/with comparison, unified-core wording, GPL-only current-facing
copy, live video link, and absence of the phrase `earlier MIT license`.

- [ ] **Step 2: Run the package test and confirm it fails**

Run: `python -m pytest tests/test_plugin_package.py -q`

Expected: failure because the current README does not yet contain the problem
narrative and still contains historical license wording.

- [ ] **Step 3: Merge the attached narrative with the current README**

Use this exact leading statement:

```markdown
> **Codex says "done." Gate checks whether that is true.**
```

Preserve current commands and evidence values, add the approved source-backed
problem sections, and state that the plugin installs and invokes an allowlisted
copy of the same `gate.py` and `gatelib/` enforcement core used by the CLI.

- [ ] **Step 4: Run the package test and confirm it passes**

Run: `python -m pytest tests/test_plugin_package.py -q`

Expected: all package tests pass with only the documented Windows plugin-cache
skip if applicable.

### Task 2: Audit the release for confirmed product defects

**Files:**
- Review: `scripts/install_plugin.py`
- Review: `scripts/gate_plugin.py`
- Review: `gate.py`
- Review: `gatelib/`
- Review: `tests/test_plugin_launcher.py`
- Review: `tests/test_plugin_package.py`

**Interfaces:**
- Consumes: plugin and CLI entry points from the same checkout.
- Produces: reproducible findings and regression fixes only when confirmed.

- [ ] **Step 1: Run focused plugin tests before review**

Run:

```powershell
python -m pytest tests/test_plugin_launcher.py tests/test_plugin_package.py -q
```

Expected: existing tests pass; any failure is investigated before documentation
or publication continues.

- [ ] **Step 2: Review security and correctness boundaries**

Confirm package allowlisting, symlink rejection, marketplace preservation,
trusted interpreter selection, external state placement, `shell=False`, task
path handling, platform rejection, and exact CLI delegation.

- [ ] **Step 3: Reproduce and fix confirmed findings using red-green tests**

For each confirmed issue, add one focused failing test, run that exact test to
observe failure, implement the minimum fix, and rerun the test. If no issue is
confirmed, record `No confirmed runtime defect found` in the final evidence.

- [ ] **Step 4: Decide the version from evidence**

If runtime or packaged behavior changes, update `.codex-plugin/plugin.json` to
`0.2.1` and update exact version assertions. If changes are documentation-only,
retain `0.2.0`.

### Task 3: Verify installation from the branch that will become master

**Files:**
- Modify only if evidence reveals an error: `docs/PLUGIN_GUIDE.md`
- Update: `docs/evidence/plugin_test_results.txt`

**Interfaces:**
- Consumes: feature branch package that will be fast-forwarded to `master`.
- Produces: native and WSL installation evidence for the same commit.

- [ ] **Step 1: Rebuild and validate plugin assets**

Run:

```powershell
python scripts/build_plugin_assets.py
git diff --exit-code -- assets
python C:/Users/Gathu/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

Expected: assets are unchanged and plugin validation passes.

- [ ] **Step 2: Install from the current checkout on native Windows**

Run: `python scripts/install_plugin.py`

Expected: Codex reports `gate@personal`; native `audit` works, while native
`doctor` and `run` reject the unsupported platform.

- [ ] **Step 3: Install and test from the same checkout in WSL 2**

Run the installer with the trusted WSL virtual-environment Python, then invoke
the installed `doctor` against a Git repository and independently validate the
checked-in live audit.

Expected: installation, discovery, doctor, and audit succeed from the package
copied from the branch that will become `master`.

### Task 4: Upload and publish the live YouTube demo

**Files:**
- Read: `docs/video/gate-real-project-live.mp4`
- Read: `docs/evidence/real_project_video/README.md`

**Interfaces:**
- Consumes: verified MP4 and integrity metadata.
- Produces: one public YouTube watch URL.

- [ ] **Step 1: Verify the upload file immediately before transmission**

Run:

```powershell
(Get-FileHash docs/video/gate-real-project-live.mp4 -Algorithm SHA256).Hash
```

Expected: `AC7240A101F72531E3CA69D6B601B5839C91318C1DC3D403660D229C23D26076`.

- [ ] **Step 2: Upload through authenticated YouTube Studio**

Set the title to `Gate v2: Codex Says Done. Gate Verifies It. | Live Project Demo`,
use the approved problem/evidence/integrity description, mark it not made for
kids, and select Public visibility.

- [ ] **Step 3: Verify publication**

Reopen the resulting watch URL and confirm the title, public visibility,
duration, description links, and playable video.

### Task 5: Update the published Devpost project

**Files:**
- No repository file is changed by this task.

**Interfaces:**
- Consumes: final YouTube watch URL and README narrative.
- Produces: Devpost project version with matching primary video and copy.

- [ ] **Step 1: Read the current editable project**

Use Devpost project `1356174` and preserve its published OpenAI Build Week
association.

- [ ] **Step 2: Replace the description and primary video**

Lead with the real developer problem and source evidence, explain Gate's
protected acceptance boundary, include CLI/plugin instructions and live proof,
and set `video_url` to the new public YouTube watch URL.

- [ ] **Step 3: Re-read and verify Devpost state**

Expected: state remains `published`, OpenAI Build Week remains listed, the five
source links and audit root are present, and `video_url` matches YouTube.

### Task 6: Verify, commit, merge, and publish master

**Files:**
- Update: changed README, tests, evidence, and any confirmed focused bug fix.

**Interfaces:**
- Consumes: all completed publication tasks.
- Produces: one final commit shared by feature branch, `master`, and origin.

- [ ] **Step 1: Run full local verification**

Run Windows and WSL suites, package validation, audit-chain validation, media
hash verification, link checks, credential scan, `git diff --check`, and
working-tree review.

- [ ] **Step 2: Commit and push the existing feature branch**

Include the YouTube URL, audit root, and video hash in the commit message or
committed evidence.

- [ ] **Step 3: Fast-forward and push master**

Run `git merge --ff-only Ash/gate-codex-plugin` from the clean main worktree,
push `master`, and verify both remote branch hashes match.

- [ ] **Step 4: Verify GitHub Actions and public master**

Expected: CI succeeds on the final `master` SHA; public README shows the
problem-led opening, installation instructions, public YouTube URL, and GPL
attribution.
