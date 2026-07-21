---
name: audit
description: Independently verify a TheUstad SHA-256 JSONL audit chain and report its record count and root. Use when the user provides an audit log, asks whether TheUstad evidence is intact, or needs the final root for external anchoring.
---

# Verify TheUstad Audit

Verify a completed TheUstad audit without changing the target repository.

1. Resolve the plugin root from this SKILL.md's absolute path. This file is at
   `<plugin-root>/skills/audit/SKILL.md`, so the plugin root is two directories
   above the directory containing this file.
2. Resolve an absolute Python 3.10+ executable.
3. Require an explicit audit log path, then invoke:

   ```text
   <absolute-python> <plugin-root>/scripts/theustad_plugin.py audit <absolute-log-path>
   ```

4. Relay the verifier output and exit code exactly. A nonzero exit is not a
   valid chain.

A `VALID` result proves internal SHA-256 chain consistency. State that later
rewriting is detectable only relative to a root anchored outside the log; do
not claim signing, HMAC, or remote attestation.
