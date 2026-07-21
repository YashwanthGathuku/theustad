---
name: run
description: Run a coding task through TheUstad's protected verification and exact-thread retry loop. Use when the user asks to verify or safely execute work in a repository. Do not use for ordinary test-only requests or to grade an already-running Codex task.
---

# Run Through TheUstad

Use this skill as `$theustad:run`.

Start a separate TheUstad-controlled child Codex session for the requested coding
task. The current task is only the launcher and result viewer.

## Procedure

1. Resolve the plugin root from this SKILL.md's absolute path. This file is at
   `<plugin-root>/skills/run/SKILL.md`, so the plugin root is two directories
   above the directory containing this file.
2. Resolve an absolute Python 3.10+ executable available in Linux, macOS, or
   WSL 2.
3. Do not edit the target repository, run the coding task, or create project
   configuration before launching TheUstad.
4. Invoke the absolute launcher path:

   ```text
   <absolute-python> <plugin-root>/scripts/theustad_plugin.py run --repo <repo> --task-text <task>
   ```

   Use `--task-file <absolute-path>` instead when the user explicitly supplied
   a task file. Add `--verifier <command>` only when the user explicitly chose
   a non-default verifier.
5. Allow the launcher to stream until it exits. Do not run a second coding
   agent in parallel.
6. Relay `FINAL`, `AUDIT_LOG`, and `AUDIT_ROOT` exactly. Do not reinterpret,
   soften, or replace TheUstad's verdict.

## Completion Rule

Claim success only when the child process returns exit code 0 and its output
contains `FINAL VERIFIED`. Every other verdict is non-success and must be
reported with the available evidence. This workflow starts a separate
TheUstad-controlled child; it does not retroactively secure the current task.
