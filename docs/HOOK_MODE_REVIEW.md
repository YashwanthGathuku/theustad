# Review of the supplied hook-mode prototype

The five supplied files were useful as a design sketch, but they were not safe
to copy into the current repository. The current project uses `theustadlib`,
and the root `theustad.py` is a complete wrapper orchestrator. Replacing it
with the 83-line prototype would remove the shipped product.

## File-by-file disposition

| Supplied file | Useful idea retained | Problem found | Current disposition |
|---|---|---|---|
| `theustad.py` | `enroll`, `status`, and fixed-policy `hook` commands | Imports a retired pre-TheUstad library; would overwrite the 512-line wrapper; emitted command paths were not safely quoted; no confirmed unenroll/audit workflow | Existing CLI extended compatibly; wrapper arguments still work |
| `enrollment.py` | External policy, manifest persistence, session counters | Session IDs were lossy-sanitized; state types and paths were weakly validated; active sessions reloaded mutable enrollment; no session-to-repo binding | Rebuilt as `theustadlib/enrollment.py` with hashed keys, atomic JSON, session policy copies, manifest path validation, and bindings |
| `hookadapter.py` | `SessionStart` freeze + `Stop` verification; verifier always runs; pre/post checks | Used nonexistent `Claim.matched`; created a fresh audit chain for every hook; substring-matched `SubagentStop`/`StopFailure`; defaulted missing identity; re-froze on compaction; trusted Stop cwd; scraped lagging transcripts; retry exhaustion was silent; ignored in-flight work | Rebuilt against exact documented Claude events and `last_assistant_message`; continuous validated audit; compaction-safe baseline; bound repo; visible exhaustion; background-race block |
| `INSTALL.md` | Small simulated tamper proof | Referenced a retired pre-TheUstad library, unsafe `python -m pytest -q`, and a stale `159 passed, 1 skipped` result | Replaced by `docs/HOOK_MODE_GUIDE.md`; current full suite evidence is generated locally |
| `HOOK_MODE_PROMPTS.md` | Evidence-first sequence and adversarial scenario list | Targeted old layout; treated ignored bytecode as harmless; contradicted itself on `PASS_NO_CLAIM`; called simulated payloads a reference implementation; did not resolve same-user/bootstrap limits | Requirements absorbed into code/tests/spec; guide now separates documentation fixtures from live proof |

## Security corrections implemented

1. **Wrapper preserved.** Hook management is an additive CLI dispatch path.
2. **Fixed invocation authority.** Hook commands reject repo, verifier,
   protection, timeout, policy, and state options before reading stdin.
3. **External enrollment.** User policy and session state default to
   `~/.theustad`, and enrollment refuses a state home inside the target repo.
4. **Session binding.** A hash-keyed `vendor + session_id` record binds Stop to
   the original canonical repo, so a subdirectory cwd cannot redirect checks.
5. **Immutable active policy.** The enrolled policy is copied into session
   state at the first SessionStart; re-enrollment cannot change that session.
6. **One baseline.** Resume, clear, and compact SessionStart events reopen the
   session and never freeze changed protected files as a new truth.
7. **Current message field.** Claude Stop's documented
   `last_assistant_message` drives claim labeling; asynchronous transcript
   scraping was removed.
8. **Exact events.** Only `SessionStart` and `Stop` parse. Similar names do not.
9. **Continuous audit.** Every process validates and resumes the same chain;
   a rewritten record blocks further appends.
10. **Verifier integrity.** The current absolute `sys.executable -I -B -m
    pytest -q` default remains; no broad pycache ignore can hide a planted
    executable artifact.
11. **Race checks.** Protected inputs are checked before and after verification;
    non-empty background tasks or scheduled session wakeups defer verification.
12. **Visible terminal state.** Retry exhaustion allows the host to end but
    emits and audits `FINAL RETRY_EXHAUSTED` plus the root. It never becomes
    `VERIFIED`.
13. **Honest boundary.** User-level external state is not safe from an
    unrestricted same-user process, and no hook can report its own prior
    disablement. Managed host policy, wrapper mode, or CI is required for that
    stronger boundary.

## Evidence added

- official-document Claude fixtures under `tests/fixtures/hooks/claude/`;
- enrollment and serialization tests;
- exact event and malformed-state tests;
- compaction, cwd, re-enrollment, injection, retry, background-task, and
  verifier-time tamper regressions;
- full CLI lifecycle tests for honest verification, deleted-test restoration,
  project hook-disable configuration, and chain validation.

The remaining promotion requirement is a live Claude Code schema capture and a real
`TAMPERED -> VERIFIED` recording. Until then, hook mode is experimental and
documentation-fixture tested, not vendor-version certified.
