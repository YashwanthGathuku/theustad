# Task 2 Evidence: Explicit JavaScript Verifier

Implemented the dependency-free JavaScript fixture, the `js_honest` fake-agent action, and the B1 end-to-end proof. The test resolves `npm` to an absolute path and supplies it with `--verifier`; it does not use verifier auto-detection. It uses `shell=False`, requires exactly one `VERIFIED` verdict and exit `0`, verifies one passing npm test, and checks unchanged SHA-256 values for `tests`, `package.json`, and `package-lock.json`.

## TDD Red

Command:

```text
python -m pytest tests/test_custom_verifier_e2e.py -q
```

Relevant exact output before adding `js_honest`:

```text
fake_codex.py: error: argument scenario: invalid choice: 'js_honest' (choose from demo3, naive2, crash, assertion_gut, conftest_poison, no_claim, config_poison, honest, reset)
ROUND 1 AGENT_ERROR
FINAL AGENT_ERROR
1 failed in 1.18s
```

## Verification

```text
python -m pytest tests/test_custom_verifier_e2e.py -q
.                                                                        [100%]
1 passed in 5.91s

python -m pytest tests/test_e2e_rehearsal.py -q
.........                                                                [100%]
9 passed in 47.49s
```

Both commands also emitted existing environment warnings from `requests` and `pytest-asyncio`; neither test failed or skipped.
