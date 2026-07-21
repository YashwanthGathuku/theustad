# TheUstad Demo and Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish TheUstad 1.0 from the renamed `master` with accurate CLI/plugin documentation, a fresh real-project Codex proof, a narrated and captioned video below three minutes, and a saved Devpost submission using the new repository and video URLs.

**Architecture:** Refresh documentation from tested canonical commands, prepare clean clones of the pinned iniconfig project, and capture one real TheUstad plugin run plus concise deterministic tamper/audit demonstrations. Preserve raw output separately, render narration and captions over the screen capture, verify media streams and integrity, then publish only after a fresh-clone installation succeeds from public `master`.

**Tech Stack:** Markdown, Bash, PowerShell, Python, Codex CLI/plugin, WSL 2, pytest, FFmpeg/FFprobe, Windows SAPI narration, Git/GitHub, YouTube, Devpost.

## Global Constraints

- Public name is `TheUstad`; canonical commands are `theustad.py`, `theustad@personal`, and `$theustad:*`.
- The standalone CLI and plugin must use the same `theustad.py` and `theustadlib` enforcement core.
- Keep all active installation commands on `https://github.com/YashwanthGathuku/theustad.git` and branch `master`.
- State Linux, macOS, and WSL 2 support; do not claim native Windows agent-run support.
- Describe `VERIFIED` as proof that the configured protected verifier passed for an explicit claim, not universal software correctness.
- Label scripted attack demonstrations as deterministic adversarial rehearsals.
- Voiceover must explicitly cover what was built, how Codex was used, and that GPT-5.6 was used during building and red-teaming.
- Final video duration must be less than 180 seconds and contain both H.264 video and audible AAC audio.
- Burn in captions and keep a matching `.srt` sidecar and narration transcript.
- Do not overwrite legacy Gate videos, transcripts, checksums, audit logs, or published roots.
- Devpost must remain visibly submitted after the final edits are saved.

## File Map

- Modify `README.md`: TheUstad value, CLI/plugin setup, migration, evidence, video, and submission links.
- Modify `docs/PLUGIN_GUIDE.md`: canonical installation, use, custom verifier, upgrade, and removal instructions.
- Modify `docs/demo/README.md`: renamed real-project proof and honest boundaries.
- Modify `docs/demo/prepare_wsl_demo.sh`: TheUstad checkout, state, and virtualenv names.
- Rename `docs/demo/run_gate_cli_wsl.sh` to `docs/demo/run_theustad_cli_wsl.sh`.
- Rename `docs/demo/run_gate_plugin_wsl.sh` to `docs/demo/run_theustad_plugin_wsl.sh`.
- Modify `docs/demo/run_no_gate_wsl.sh`: call the comparison `without TheUstad` while forbidding both canonical and legacy launchers.
- Create `docs/video/run_theustad_demo_wsl.sh`: timed capture sequence.
- Create `docs/video/record_theustad_demo.ps1`: desktop capture and marker handling.
- Create `docs/video/build_theustad_narrated_demo.ps1`: narration, captions, render, media validation, and checksum.
- Create after recording `docs/video/theustad-build-week-demo.mp4`.
- Create after rendering `docs/video/theustad-build-week-demo.en.srt`.
- Create `docs/video/theustad-build-week-demo-transcript.txt`.
- Modify `docs/video/README.md`: current TheUstad artifact and legacy-video section.
- Create after execution `docs/evidence/theustad-1.0/real-project/*`.
- Create after execution `docs/evidence/theustad-1.0/video/*`.
- Modify `tests/test_plugin_package.py`: current README/demo requirements.
- Create `tests/test_docs_release.py`: active URLs, commands, media references, and honesty claims.
- Create after publication `docs/evidence/theustad-1.0/publication.txt`.

---

### Task 1: Rewrite Current Documentation Around TheUstad

**Files:**
- Modify: `README.md`
- Modify: `docs/PLUGIN_GUIDE.md`
- Modify: `docs/demo/README.md`
- Modify: `docs/video/README.md`
- Modify: `tests/test_plugin_package.py`
- Create: `tests/test_docs_release.py`

**Interfaces:**
- Consumes: tested commands and evidence roots from the previous two plans.
- Produces: one canonical public onboarding path plus an explicit Gate migration section.

- [ ] **Step 1: Write failing documentation assertions**

Create `tests/test_docs_release.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_uses_canonical_release_links_and_commands():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    required = (
        "# TheUstad",
        'Codex says "done." TheUstad checks whether that is true.',
        "https://github.com/YashwanthGathuku/theustad.git",
        "$theustad:doctor",
        "$theustad:run",
        "$theustad:audit",
        "python theustad.py --repo",
        "theustad@personal",
        "THEUSTAD_PYTHON",
        "Linux, macOS, or WSL 2",
        "Formerly Gate",
        "PASS_NO_CLAIM",
        "custom verifier",
        "GPL-3.0-or-later",
    )
    for value in required:
        assert value in text


def test_current_docs_do_not_recommend_legacy_commands():
    for relative in ("README.md", "docs/PLUGIN_GUIDE.md", "docs/demo/README.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "git clone https://github.com/YashwanthGathuku/gate" not in text
        assert "codex plugin add gate@personal" not in text


def test_docs_state_honesty_boundaries():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "does not make software 100% correct" in text
    assert "deterministic scripted adversarial rehearsal" in text
    assert "explicit custom verifier" in text
    assert "automatic framework detection" not in text
```

- [ ] **Step 2: Run documentation tests and require old-name failures**

```powershell
python -m pytest tests/test_docs_release.py tests/test_plugin_package.py -q
```

Expected: failures identify current Gate headings, commands, paths, and URLs.

- [ ] **Step 3: Rewrite README in this exact section order**

Use these top-level sections:

```text
TheUstad
Why TheUstad exists
What changes with TheUstad
Three-minute proof
Quick start
Choose CLI or Codex plugin
Standalone CLI
Codex plugin
Custom verifiers and protected inputs
Upgrade from Gate
Audit verification
Evidence and reproducibility
Supported platforms
Security boundaries
License and attribution
OpenAI Build Week
```

Keep the verified public evidence links already in the README. Replace active
product prose and repository links. Move old Gate video URLs into a clearly
named historical-evidence paragraph. Include copy-paste canonical install,
remove, CLI, plugin-skill, custom npm verifier, and audit commands.

- [ ] **Step 4: Rewrite the plugin and demo guides from tested commands**

The plugin guide must cover fresh install, WSL 2, `$theustad:doctor`,
`$theustad:run`, `$theustad:audit`, `--protect-add`, upgrade from an existing
Gate install, canonical removal, and audit-only native Windows behavior.

The demo guide must keep the pinned iniconfig commit
`77db208ab4ae0cd2061d909fe222a1db72867850`, identify the acceptance test as
human-authored and not an upstream issue, and provide separate ordinary,
standalone CLI, and plugin reproduction commands.

- [ ] **Step 5: Update the video index without deleting old artifacts**

Make `theustad-build-week-demo.mp4` the pending/current artifact once generated.
Move existing videos under `Historical Gate recordings`, retaining their URLs,
digests, and honesty labels.

- [ ] **Step 6: Run documentation, naming, and link-source tests**

```powershell
python -m pytest tests/test_docs_release.py tests/test_plugin_package.py tests/test_active_naming.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit the documentation migration**

```powershell
git add README.md docs/PLUGIN_GUIDE.md docs/demo/README.md docs/video/README.md tests/test_docs_release.py tests/test_plugin_package.py
git commit -m "docs: publish TheUstad setup and migration guidance"
```

### Task 2: Rename and Harden the Real-Project Harness

**Files:**
- Modify: `docs/demo/prepare_wsl_demo.sh`
- Rename: `docs/demo/run_gate_cli_wsl.sh` to `docs/demo/run_theustad_cli_wsl.sh`
- Rename: `docs/demo/run_gate_plugin_wsl.sh` to `docs/demo/run_theustad_plugin_wsl.sh`
- Modify: `docs/demo/run_no_gate_wsl.sh`
- Create: `tests/test_demo_scripts.py`

**Interfaces:**
- Consumes: canonical checkout, installed plugin, pinned iniconfig fixture, and external state root.
- Produces: three clean clones and raw ordinary/CLI/plugin evidence under a caller-supplied directory.

- [ ] **Step 1: Write script-content tests**

Create `tests/test_demo_scripts.py` that reads all four scripts and requires:

```python
assert "theustad.py" in cli_script
assert "THEUSTAD_ROOT" in cli_script
assert "THEUSTAD_STATE_HOME" in plugin_script
assert "theustad@personal" in plugin_script
assert "$theustad:run" in plugin_script
assert "gate.py" not in no_gate_script
assert "theustad.py" not in no_gate_script
assert "77db208ab4ae0cd2061d909fe222a1db72867850" in prepare_script
```

Also require every subprocess-bearing script to start with
`set -euo pipefail`, quote path variables, record timestamps and exit codes,
and reject a dirty target repository.

- [ ] **Step 2: Run script tests and require missing/old-name failures**

```powershell
python -m pytest tests/test_demo_scripts.py -q
```

Expected: failures until scripts are renamed and updated.

- [ ] **Step 3: Rename and update harness variables and paths**

Run:

```powershell
git mv docs/demo/run_gate_cli_wsl.sh docs/demo/run_theustad_cli_wsl.sh
git mv docs/demo/run_gate_plugin_wsl.sh docs/demo/run_theustad_plugin_wsl.sh
```

Use these defaults:

```bash
theustad_root="${THEUSTAD_ROOT:-$HOME/code/theustad}"
demo_home="${DEMO_HOME:-$HOME/theustad-demo-code}"
venv_home="${DEMO_VENV_HOME:-$HOME/.local/share/theustad-demo}"
evidence="${DEMO_EVIDENCE:-$HOME/theustad-demo-evidence}"
state_home="${THEUSTAD_STATE_HOME:-$HOME/.local/state/theustad-demo}"
```

The no-TheUstad prompt must explicitly forbid TheUstad and legacy Gate skills
or launchers. Its summary records `THEUSTAD_VERDICT NONE`, `AUDIT_LOG NONE`,
and `AUDIT_ROOT NONE`.

- [ ] **Step 4: Keep target inputs identical across modes**

Preparation must create three full clones, check out the pinned commit, add the
same acceptance test, commit it, install the same pytest requirement, and
require the same `1 failed, 49 passed` baseline in each clone. Record each
baseline commit and SHA-256 of the acceptance test.

- [ ] **Step 5: Run shell syntax checks and Python tests**

```powershell
wsl.exe -d Ubuntu-24.04 -u gathu -- bash -lc 'cd /home/gathu/code/theustad && bash -n docs/demo/*.sh'
python -m pytest tests/test_demo_scripts.py -q
```

Expected: syntax checks and script-content tests pass.

- [ ] **Step 6: Commit the harness migration**

```powershell
git add docs/demo tests/test_demo_scripts.py
git commit -m "test: migrate the real-project harness to TheUstad"
```

### Task 3: Capture Fresh Real-Project and Plugin Evidence

**Files:**
- Create after execution: `docs/evidence/theustad-1.0/real-project/README.md`
- Create after execution: `docs/evidence/theustad-1.0/real-project/no_theustad_*`
- Create after execution: `docs/evidence/theustad-1.0/real-project/theustad_cli_*`
- Create after execution: `docs/evidence/theustad-1.0/real-project/theustad_plugin_*`

**Interfaces:**
- Consumes: clean prepared clones and canonical plugin installation.
- Produces: actual Codex control, standalone CLI, plugin, diff, test, thread, verdict, and audit evidence.

- [ ] **Step 1: Prepare all clones and capture the common baseline**

Inside WSL:

```bash
cd "$HOME/code/theustad"
bash docs/demo/prepare_wsl_demo.sh
```

Expected: three clean clones, each with the same committed acceptance test and
`1 failed, 49 passed` baseline.

- [ ] **Step 2: Run ordinary Codex without either plugin**

```bash
codex plugin remove theustad@personal --json || true
codex plugin remove gate@personal --json || true
bash docs/demo/run_no_gate_wsl.sh
```

Expected: project tests pass after Codex work; summary explicitly reports no
TheUstad verdict, log, or root. Preserve the complete JSONL and diff.

- [ ] **Step 3: Run the canonical standalone CLI in a fresh clone**

```bash
bash docs/demo/run_theustad_cli_wsl.sh
```

Expected: terminal `FINAL VERIFIED`, exit 0, exact child thread, full verifier
output, `AUDIT_ROOT`, and independently `VALID` chain.

- [ ] **Step 4: Install the canonical plugin and run the plugin path**

```bash
"$HOME/.local/share/theustad-demo/theustad-plugin-venv/bin/python" \
  scripts/install_plugin.py
codex plugin list --json
bash docs/demo/run_theustad_plugin_wsl.sh
```

Expected: `theustad@personal` enabled and the plugin run reaches a genuine
terminal verdict. Do not manufacture retries if Codex completes honestly in
one round.

- [ ] **Step 5: Copy raw evidence into the repository**

Copy files without editing their contents. Build `README.md` from recorded
facts: timestamps, pinned commit, target baseline commit, Codex thread IDs,
test counts, `FINAL`, audit paths, roots, chain validation, and diffs. State
that ordinary Codex may solve the task correctly; TheUstad's demonstrated
value is the independent protected decision and audit record.

- [ ] **Step 6: Validate copied audits and checksums**

```bash
python3 verify_chain.py docs/evidence/theustad-1.0/real-project/theustad_cli_audit.jsonl
python3 verify_chain.py docs/evidence/theustad-1.0/real-project/theustad_plugin_audit.jsonl
find docs/evidence/theustad-1.0/real-project -type f -print0 | sort -z | xargs -0 sha256sum
```

Expected: both audits are `VALID`; store the checksum list excluding the list
file itself.

- [ ] **Step 7: Commit the real-project evidence**

```powershell
git add docs/evidence/theustad-1.0/real-project
git commit -m "test: capture TheUstad real-project evidence"
```

### Task 4: Build the Under-Three-Minute Recording Harness

**Files:**
- Create: `docs/video/run_theustad_demo_wsl.sh`
- Create: `docs/video/record_theustad_demo.ps1`
- Create: `tests/test_video_scripts.py`

**Interfaces:**
- Consumes: committed real-project and robustness evidence plus a clean plugin target clone.
- Produces: a raw 1920x1080 desktop recording and timestamp marker file.

- [ ] **Step 1: Write video-script contract tests**

Create `tests/test_video_scripts.py` requiring:

```python
assert "THEUSTAD 1.0 - CODING CLAIMS NEED PROOF" in wsl_script
assert "WITHOUT THEUSTAD" in wsl_script
assert "$theustad:run" in wsl_script
assert "TAMPERED" in wsl_script
assert "BROKEN" in wsl_script and "VALID" in wsl_script
assert "ffmpeg" in powershell_script
assert "gdigrab" in powershell_script
assert "-draw_mouse 0" in powershell_script
assert "180" not in configured_duration
```

- [ ] **Step 2: Implement a concise honest WSL sequence**

`run_theustad_demo_wsl.sh` must display these scenes and append epoch markers:

```text
intro
control
install
plugin_start
plugin_result
tamper
audit
closing
```

The control scene reads the newly captured ordinary-Codex summary and labels
it `CAPTURED REAL CONTROL RUN`; it does not rerun a second lengthy model task.
The plugin scene launches one fresh real `$theustad:run` through `codex exec`
against the clean plugin clone. The tamper scene runs A2 live as a labeled
deterministic rehearsal and proves `conftest.py` is absent afterward. The audit
scene verifies an edited copy as `BROKEN` and the untouched log as `VALID`.

- [ ] **Step 3: Implement fail-closed desktop capture**

`record_theustad_demo.ps1` resolves the repository from its own location,
starts FFmpeg desktop capture at 1920x1080/12 fps, starts one maximized hidden-
setup PowerShell terminal that invokes WSL, waits no more than 12 minutes for
the done marker, stops FFmpeg cleanly, and fails when the WSL status is nonzero.
Write the raw file as `docs/video/theustad-build-week-demo-raw.mp4`.

- [ ] **Step 4: Add marker and raw-media checks**

Require all eight markers in increasing order. Probe the raw file with:

```powershell
ffprobe -v error -show_entries stream=codec_name,width,height,duration -show_entries format=duration,size -of json docs/video/theustad-build-week-demo-raw.mp4
```

Expected: H.264 video, 1920x1080, nonzero duration and size. Raw audio is not
required because narration is added in the next task.

- [ ] **Step 5: Run script tests and WSL syntax check**

```powershell
python -m pytest tests/test_video_scripts.py -q
wsl.exe -d Ubuntu-24.04 -u gathu -- bash -n /home/gathu/code/theustad/docs/video/run_theustad_demo_wsl.sh
```

Expected: all checks pass.

- [ ] **Step 6: Commit the recording harness**

```powershell
git add docs/video/run_theustad_demo_wsl.sh docs/video/record_theustad_demo.ps1 tests/test_video_scripts.py
git commit -m "feat: add the TheUstad live demo recorder"
```

### Task 5: Render Narration, Captions, and the Final Video

**Files:**
- Create: `docs/video/build_theustad_narrated_demo.ps1`
- Create: `docs/video/theustad-build-week-demo-transcript.txt`
- Create after execution: `docs/video/theustad-build-week-demo.en.srt`
- Create after execution: `docs/video/theustad-build-week-demo.mp4`
- Create after execution: `docs/evidence/theustad-1.0/video/video_probe.json`
- Create after execution: `docs/evidence/theustad-1.0/video/video_sha256.txt`
- Create: `docs/evidence/theustad-1.0/video/README.md`

**Interfaces:**
- Consumes: raw recording and marker timestamps.
- Produces: final 175-second maximum H.264/AAC artifact, captions, transcript, probe, and checksum.

- [ ] **Step 1: Use this approved narration structure**

The transcript must communicate these exact factual claims in natural speech:

```text
TheUstad treats a coding agent's done message as a claim, not proof.
The control run is real Codex work on a pinned open-source project, but it has no protected verdict or audit root.
TheUstad installs as one Codex plugin and also keeps a standalone CLI using the same enforcement core.
The run skill freezes trusted tests and configuration outside the target repository, starts a separate child Codex task, and resumes that exact child with verifier evidence.
FINAL VERIFIED means the explicit completion claim passed the configured protected verifier; it does not mean all software is universally correct.
This conftest poisoning example is a deterministic adversarial rehearsal. TheUstad reports TAMPERED and removes the planted protected file.
Changing a copied audit record makes validation BROKEN, while the untouched SHA-256 chain remains VALID against its externally anchored root.
I used Codex with GPT-5.6 to build, test, red-team, document, and package TheUstad for OpenAI Build Week.
```

Use first-person phrasing in the final voiceover so it sounds like the project
author, while retaining every factual boundary above.

- [ ] **Step 2: Implement cue-driven narration and captions**

Create PowerShell cue objects with `Start`, `End`, and `Text`, generate the SRT
from those same objects, synthesize each segment with Windows SAPI, mix segments
at their cue offsets, and burn the generated SRT into the video. No cue may end
at or after 178 seconds.

- [ ] **Step 3: Render to a strict maximum duration**

Use FFmpeg mappings and codecs:

```text
-map 0:v:0 -map 1:a:0
-c:v libx264 -preset medium -crf 18
-c:a aac -b:a 160k
-af apad=pad_dur=178
-t 178
-movflags +faststart
```

If the raw recording is longer, trim loading/waiting sections before this
final mapping using marker-based segment selection. Never speed up verdict,
root, tamper-path, or audit-validation scenes beyond readability.

- [ ] **Step 4: Record and render**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File docs/video/record_theustad_demo.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File docs/video/build_theustad_narrated_demo.ps1
```

Expected: both commands exit 0 and produce the raw, final MP4, SRT, transcript,
probe, and checksum files.

- [ ] **Step 5: Verify duration, streams, captions, and audibility**

Run:

```powershell
ffprobe -v error -show_entries stream=index,codec_type,codec_name,channels,width,height,duration -show_entries format=duration,size -of json docs/video/theustad-build-week-demo.mp4
ffmpeg -v error -i docs/video/theustad-build-week-demo.mp4 -map 0:a:0 -af volumedetect -f null NUL
Get-FileHash -Algorithm SHA256 docs/video/theustad-build-week-demo.mp4
```

Require format duration below 180 seconds, one H.264 video stream, one AAC
audio stream with at least one channel, non-silent measured audio, 1920x1080
dimensions, and a 64-hex SHA-256 value matching `video_sha256.txt`.

- [ ] **Step 6: Watch the complete video and inspect fixed frames**

Watch from start to finish with sound enabled. Capture frames near 5, 35, 65,
100, 135, and 165 seconds and verify no terminal text, captions, verdicts, or
hashes are cropped or overlapped. Confirm narration explicitly says Codex and
GPT-5.6 and accurately labels the scripted attack.

- [ ] **Step 7: Commit final video evidence**

```powershell
git add docs/video/theustad-build-week-demo.mp4 docs/video/theustad-build-week-demo.en.srt docs/video/theustad-build-week-demo-transcript.txt docs/video/README.md docs/evidence/theustad-1.0/video
git commit -m "docs: publish the narrated TheUstad demo"
```

Keep the large raw recording outside the commit or ignored after its final
checksum and provenance are captured.

### Task 6: Push Master and Validate a Public Fresh Clone

**Files:**
- Modify only if needed after validation: `README.md`, `docs/PLUGIN_GUIDE.md`

**Interfaces:**
- Consumes: complete committed release and canonical remote.
- Produces: public `master` commit and judge-equivalent install proof.

- [ ] **Step 1: Run the release verification set**

```powershell
python -m pytest tests -q
git diff --check
git status --short
```

Inside WSL run the complete test suite again. Expected: all tests pass, no diff
errors, and no unexplained working-tree changes.

- [ ] **Step 2: Push canonical master**

```powershell
git push origin master
```

Expected: push succeeds to `YashwanthGathuku/theustad`.

- [ ] **Step 3: Clone exactly as a judge would**

Inside WSL:

```bash
rm -rf "$HOME/theustad-judge-check"
git clone https://github.com/YashwanthGathuku/theustad.git "$HOME/theustad-judge-check"
cd "$HOME/theustad-judge-check"
git branch --show-current
git rev-parse HEAD
```

Verify branch `master` and the expected pushed commit. The recursive removal is
limited to the fixed `$HOME/theustad-judge-check` path after resolving and
printing it.

- [ ] **Step 4: Install and exercise the plugin from the fresh clone**

Create a fresh external virtualenv, install pytest, run
`scripts/install_plugin.py`, require `theustad@personal` enabled, run doctor,
execute the deterministic `demo3` proof, and validate its emitted chain.

Expected: no rebuild or local source path outside the clone is required.

- [ ] **Step 5: Record fresh-clone results**

Append exact commands, commit, installation JSON, verdicts, root, validator
output, and exit codes to
`docs/evidence/theustad-1.0/fresh_clone_validation.txt`, commit, and push it.

### Task 7: Upload YouTube Video and Update Devpost

**Files:**
- Create after publication: `docs/evidence/theustad-1.0/publication.txt`
- Modify: `README.md`
- Modify: `docs/video/README.md`
- Modify: `.codex-plugin/plugin.json` only if the Devpost canonical page changes.

**Interfaces:**
- Consumes: verified final MP4, public repository, evidence roots, feedback ID, and author-controlled authenticated browser sessions.
- Produces: public/unlisted YouTube URL, updated submitted Devpost entry, and repository publication record.

- [ ] **Step 1: Upload the verified MP4 to YouTube**

Use title:

```text
TheUstad - Codex Says Done. TheUstad Checks the Proof. | OpenAI Build Week
```

Use a concise human-edited description naming the problem, CLI/plugin, real
project, deterministic attack, Codex, GPT-5.6, repository URL, verifier
limitation, and GPL-3.0-or-later license. Set visibility to Unlisted or Public,
complete processing, and open the final watch page.

- [ ] **Step 2: Verify the published video**

Play the YouTube video from beginning to end with sound. Confirm duration below
three minutes, clear narration, synchronized readable captions, visible
TheUstad name, Codex and GPT-5.6 explanation, and no processing/error banner.
Record the watch URL and verification timestamp.

- [ ] **Step 3: Update Devpost project content**

Set project name to `TheUstad`. Update repository to
`https://github.com/YashwanthGathuku/theustad`, replace the primary video with
the new YouTube URL, keep feedback session ID
`019f708d-eb32-72d0-a58d-fdd5ffcff511`, and describe:

- the verification-tax and test-tampering problem;
- completion claims as falsifiable evidence rather than prose;
- CLI and Codex plugin sharing one core;
- protected inputs, exact-thread retries, trusted verifier, restoration, and
  hash-chained audit root;
- use of Codex with GPT-5.6 during implementation and red-teaming;
- the real-project proof and deterministic attack proof;
- supported platforms and the weak-verifier limitation.

Read the final description aloud and edit phrasing that does not sound like the
author's own explanation.

- [ ] **Step 4: Save and confirm submission state**

Save every form section, return to My Projects, and require the green
`Submitted` label. Reopen the project and read back the name, repository,
video, feedback ID, and team status. Confirm every invited teammate has
accepted or state that the submission is individual.

- [ ] **Step 5: Update repository links and publication record**

Replace pending video links in README, video index, and manifest with the
verified YouTube and Devpost URLs. Write `publication.txt` with timestamp,
GitHub URL/visibility/default branch, YouTube URL/visibility/duration/audio
check, Devpost URL/submitted status, feedback ID, and the current release
commit. Do not store login tokens or private account data.

- [ ] **Step 6: Commit and push publication metadata**

```powershell
git add README.md docs/video/README.md .codex-plugin/plugin.json docs/evidence/theustad-1.0/publication.txt
git commit -m "docs: publish TheUstad Build Week submission"
git push origin master
```

### Task 8: Final Release Audit

**Files:**
- Modify only when a discovered release blocker requires a focused fix.

**Interfaces:**
- Consumes: public master, installed plugin, YouTube page, Devpost entry, and all committed evidence.
- Produces: final release status with explicit unresolved conditions.

- [ ] **Step 1: Verify the public repository from a new clone one final time**

Require README first viewport to say TheUstad, plugin manifest 1.0.0,
standalone CLI present, compatibility wrapper present, current video URL
playable, and all release evidence directories accessible.

- [ ] **Step 2: Run critical commands from that clone**

```bash
python3 -m pytest tests -q
python3 fake_codex.py reset --repo /tmp/theustad-final-demo
python3 theustad.py --repo /tmp/theustad-final-demo --task task.md \
  --cmd "python3 $PWD/fake_codex.py demo3" \
  --resume-cmd "python3 $PWD/fake_codex.py demo3 --resume {thread_id}" \
  --max-retries 3 --no-color
```

Expected: complete tests pass; final rehearsal sequence is
`FALSIFIED -> TAMPERED -> VERIFIED`; emitted chain is `VALID`.

- [ ] **Step 3: Recheck externally visible submission properties**

Confirm GitHub is public, YouTube playback has audio and captions, Devpost uses
TheUstad and the canonical URLs, individual residence/team fields are valid,
and submission status remains `Submitted`.

- [ ] **Step 4: Report completion conservatively**

Report exact test counts, skipped tests, final commit, plugin version, demo
duration, video URL, Devpost URL, feedback ID, critical audit roots, and any
remaining limitation. Do not call the release complete if any external page
cannot be read back or any required test is failing.
