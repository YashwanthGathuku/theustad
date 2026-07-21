# TheUstad 1.0 Robustness Evidence

This bundle was generated from commit `b67804c24a08fdb5ad3ac86c135bbcfe9689a870` in a fresh WSL sibling clone on Ubuntu-24.04. The run used `/home/gathu/.local/share/theustad/plugin-venv/bin/python` with `PATH=/usr/bin:/bin`, native Node `v18.19.1`, and npm `9.2.0`.

The complete suite ran once: `202 passed, 1 skipped`. The release evidence matrix ran once and produced 18 PASS scenarios. All 40 manifest entries pass SHA-256 validation. The independent legacy diff was empty, so `docs/evidence/real_project_demo`, `docs/evidence/real_project_video`, and the existing top-level evidence JSONL files were unchanged.

## Scenarios

The scripted scenarios are deterministic fixture-based checks.

- A1: source-file tampering is detected and the changed test file is restored; audit chain is valid; final verdict `TAMPERED`.
- A2: `conftest.py` tampering is detected and restored; audit chain is valid; final verdict `TAMPERED`.
- A3: a nonzero run with no claim is classified `PASS_NO_CLAIM`; audit chain is valid.
- A4: an agent crash is classified `AGENT_ERROR`; audit chain is valid.
- A5: `pytest.ini` tampering is detected and restored; audit chain is valid; final verdict `TAMPERED`.
- B1: the JavaScript project passes with protected files unchanged; `VERIFIED`. This is explicit custom-verifier support, not automatic verifier detection.
- B2: an honest Python run completes and is `VERIFIED`.
- B3-1 through B3-10: the retry sequence is `FALSIFIED,TAMPERED,VERIFIED`, with valid audit chains.
- B4: the copied audit chain is `BROKEN`, while the untouched original remains `VALID`.

The ten B3 audit roots are:

```text
B3-1  725c672d030e7505387eb82f897a086e6f6522148ce84ea114affbb49f8664c3
B3-2  8cf90256f8e56a181a0605a8fe47709ba51a190339002b6bb2f2468a79b82c82
B3-3  66e177ee767a314602d7b983b0782d115a8ffdaf05798af9a4841c14eb080234
B3-4  bae98a8536078a2ec3ef3dba4ad02a007bf124452311f3e12eba490ba4525c7d
B3-5  1f2d7e7d919717bc7022f4f674506b07340b82ddc94874c52d2032352ad8cce4
B3-6  be1e0c94f9776869e1d10d006a5e938992e2949766a44135d5cf05c8e479bc30
B3-7  2567c91adb60ef993872f58bc69344e7152523fc2c1df5a334792a814446a787
B3-8  a174781ba2960fb19fbe66cef5789db745255905522a55dd7b2f90045bb7d1aa
B3-9  156df2d82f28d61f1a46f6152c05b442c309c5412b584fe12f62316158a84e1d
B3-10 0e99a1a164824ec78785a66d1a41284ec23b67e322ca891838a9eadd427a6935
```

B4's untouched original root is `725c672d030e7505387eb82f897a086e6f6522148ce84ea114affbb49f8664c3`.

## Reproduction

From Ubuntu-24.04 WSL, using a fresh clone at the source commit:

```bash
export PATH=/usr/bin:/bin
git clone --no-local /mnt/c/Users/Gathu/Projects/gate /mnt/c/Users/Gathu/Projects/gate-wsl-evidence-20260721
cd /mnt/c/Users/Gathu/Projects/gate-wsl-evidence-20260721
git checkout --detach b67804c24a08fdb5ad3ac86c135bbcfe9689a870
mkdir -p docs/evidence/theustad-1.0/robustness
/home/gathu/.local/share/theustad/plugin-venv/bin/python -m pytest tests -q 2>&1 | tee docs/evidence/theustad-1.0/robustness/test_suite.txt
/home/gathu/.local/share/theustad/plugin-venv/bin/python scripts/run_release_evidence.py --output docs/evidence/theustad-1.0/robustness
cd docs/evidence/theustad-1.0/robustness
sha256sum -c sha256sums.txt
```

The Git commit containing this evidence bundle is the external anchor. The bundle commit is recorded in the follow-up commit below; the follow-up cannot be part of its own hash.

Evidence-content commit: `PENDING_FIRST_COMMIT`

Anchor-reference commit: `PENDING_FOLLOW_UP_COMMIT`
