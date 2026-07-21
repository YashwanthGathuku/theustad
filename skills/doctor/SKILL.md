---
name: doctor
description: Check whether the current project can run TheUstad, including platform, Git, Python, Codex CLI, authentication, resume flags, pytest, and external state paths. Use before a first TheUstad run or when it cannot start.
---

# TheUstad Doctor

Run TheUstad's read-only prerequisite check without editing the target repository.

1. Resolve the plugin root from this SKILL.md's absolute path. This file is at
   `<plugin-root>/skills/doctor/SKILL.md`, so the plugin root is two directories
   above the directory containing this file.
2. Resolve an absolute Python 3.10+ executable.
3. Invoke:

   ```text
   <absolute-python> <plugin-root>/scripts/theustad_plugin.py doctor --repo <repo>
   ```

4. Add `--verifier <command>` only when checking an explicit custom verifier.
5. Relay every `GATE_DOCTOR_*` or `GATE_PLUGIN_ERROR` line exactly.

Do not bypass a native Windows rejection. TheUstad requires Linux, macOS, or WSL 2
because its completion contract includes process-group termination.
