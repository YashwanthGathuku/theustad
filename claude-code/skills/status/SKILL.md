---
name: status
description: Report whether TheUstad protects the current repository in Claude Code (enrollment, verifier, protected inputs, installed hooks) and how a person enrolls it. Read-only. Use when the user asks whether TheUstad is active or why a Stop was blocked.
---

# TheUstad status

Run this read-only command and report its output exactly:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/theustad.py" status --repo "${CLAUDE_PROJECT_DIR}"
```

- `ENROLLED`: TheUstad verifies every completion claim in this repository at
  Stop, using the verifier shown. Report the verifier and the protected
  pattern count.
- `NOT_ENROLLED` (exit 1): this repository is not protected. Tell the user
  they can enroll it from their own terminal, then start a new Claude Code
  session:

  ```text
  python3 "${CLAUDE_PLUGIN_ROOT}/theustad.py" enroll --repo "${CLAUDE_PROJECT_DIR}" --calibrate
  ```

Do not run `enroll`, `unenroll`, `install-hooks`, or `uninstall-hooks`
yourself. They set the policy that judges your own work, so a person runs
them.
