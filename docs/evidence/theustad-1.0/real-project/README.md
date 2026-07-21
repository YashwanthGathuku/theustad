# TheUstad 1.0 real-project evidence

Captured in Ubuntu 24.04 WSL 2 on 2026-07-21 against pytest-dev/iniconfig at
upstream commit `77db208ab4ae0cd2061d909fe222a1db72867850`.

The added acceptance test is human-authored for this demonstration. It is not
an upstream iniconfig issue or upstream test. All three clones contain the same
test bytes with SHA-256
`4dbb69ddcfedad582e5ef445fd5fa561428d6ba0f7b7444eeda591d299b2bfc4`.
Each clean baseline reported `1 failed, 49 passed`.

| Mode | Baseline commit | Codex child thread | Result | Audit root |
| --- | --- | --- | --- | --- |
| Ordinary Codex without TheUstad | `8fc8c5ebdf193c56c75f38390920b1197ae47969` | `019f8333-6be1-7471-81ab-2e4b00d5cdc7` | `50 passed`; TheUstad verdict/log/root `NONE` | `NONE` |
| Standalone TheUstad CLI | `2230a9ca2dd530377251969b04d45adbf8609b53` | `019f8334-7ed7-7ea0-84a0-a46ec1c59230` | `FINAL VERIFIED`; `50 passed`; chain `VALID` | `186f8e6827f26fbd57a2dae4d435bccde4471a92e0f3573f696162d975ec551d` |
| TheUstad Codex plugin | `190c9368295d2ec8ab473249a4d17ce61aa17614` | `019f8339-69f0-7f61-afe8-af73be4e1edc` | `FINAL VERIFIED`; `50 passed`; chain `VALID` | `8248b6245bca6c5d75b5b1b39224b200dd2da5b8f97adbeb695a681c59af30f0` |

Ordinary Codex solved this task correctly. TheUstad's demonstrated value is
not a claim that the agent cannot succeed without it. The added value is an
independent completion decision, protected-input enforcement, an exact child
thread, and a hash-chained audit record whose root can be anchored outside the
log.

Raw console/JSONL, baseline and final test output, diffs, Git status, plugin
discovery, summaries, copied audits, independent chain checks, and preparation
records are stored beside this file. `sha256sums.txt` covers every evidence
file except itself.

Reproduce with the commands in `docs/demo/README.md`. The harness pins the
upstream commit and refuses dirty target repositories.
