# Check pull requests in CI

CI mode needs no agent integration. Codex, Claude Code, opencode, aider, a
script or a person: whatever wrote the change, it reaches you as a pull
request, and TheUstad asks the question a careful reviewer would.

> Do the acceptance tests this change started from still pass, unedited, on
> its code?

For each pull request, TheUstad:

1. Finds the commit the change started from (the merge base with your base
   branch).
2. Reads the protected inputs (tests and test configuration) and the policy
   file `.theustad.json` from **that commit's git objects**, never from the
   pull request's checkout.
3. Reports every protected file the change **modified or deleted** as
   tampering, and puts the original back before testing.
4. Leaves **new** protected files out of the acceptance run, so adding a test
   is never an offence and a new test cannot change how the old ones behave.
5. Runs the base commit's tests on the base commit to record which tests
   exist (the [test census](../README.md#test-census)), then runs them on the
   change and requires every one to run again.
6. Writes a verdict, a job summary and a SHA-256 audit chain.

| Verdict | Meaning | Exit |
|---|---|---|
| `VERIFIED` | The original acceptance tests ran and passed on this change | 0 |
| `FALSIFIED` | They failed, or the census shows they did not all run | 1 |
| `TAMPERED` | The change edits or deletes the tests, test configuration, policy or workflow that judge it, or the tests changed protected files while running | 1 |
| `VERIFIER_TIMEOUT` | The tests did not finish within the timeout | 1 |
| error | The check could not run (no shared history, invalid policy, ...) | 2 |

## Add it to a repository

```yaml
# .github/workflows/theustad.yml
name: TheUstad
on:
  pull_request:

permissions:
  contents: read

jobs:
  theustad:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # the merge base must be in the clone
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install pytest -r requirements.txt   # your own install step
      - uses: YashwanthGathuku/theustad@<full-commit-sha>
        with:
          python: python
```

Pin the action to a full commit SHA. The action's own code then comes from
TheUstad's repository at that commit, so a pull request cannot edit the
checker.

Then make the job a **required status check** in your branch protection or
ruleset, so a pull request cannot merge without a `VERIFIED` result.

Action inputs, all optional:

| Input | Default | Purpose |
|---|---|---|
| `base` | the pull request's base commit | Branch or commit to compare against on other events; ignored on a pull request |
| `verifier` | `.theustad.json`, then isolated pytest | Test command, run without a shell |
| `protect-add` | none | Extra protected patterns, space-separated |
| `census` | `true` | `false` skips the census and its run on the base commit |
| `timeout` | `.theustad.json`, then 1800 | Seconds the tests may run, each time |
| `python` | `python3` | Python 3.10+ for TheUstad and the default verifier |

Outputs: `verdict`, `audit-log`, and `result` (the path of the JSON result).
Upload the audit log as an artifact if you want to keep it:

```yaml
      - uses: YashwanthGathuku/theustad@<full-commit-sha>
        id: theustad
      - if: always()
        uses: actions/upload-artifact@v4
        with:
          name: theustad-audit
          path: ${{ steps.theustad.outputs.audit-log }}
```

## Configure it with `.theustad.json`

Commit the policy to your default branch. It is read from the base commit, so
a pull request that edits it changes nothing about its own check. The edit is
reported as `TAMPERED`, and a person reviews it.

```json
{
  "verifier": "python -m pytest -q",
  "protect_add": ["fixtures/**"],
  "census": true,
  "timeout": 900
}
```

| Key | Type | Meaning |
|---|---|---|
| `verifier` | string | Test command, parsed without a shell |
| `protect` | list of patterns | **Replaces** the default protected patterns |
| `protect_add` | list of patterns | Adds to them |
| `census` | boolean | Run the test census (pytest verifiers only) |
| `timeout` | number | Seconds the tests may run, each time |

An unknown key is an error rather than something to ignore. A misspelt key in
a security policy would otherwise silently keep the default.

Default protected patterns: `tests/**`, `conftest.py`, `**/conftest.py`,
`pytest.ini`, `pyproject.toml`, `setup.cfg`, `tox.ini`, `pytest.py`,
`pytest/**`, `sitecustomize.py`, `usercustomize.py`, `.github/workflows/**`, and
`.theustad.json` itself.

For a JavaScript project, name the test runner directly and protect its
configuration:

```json
{
  "verifier": "npx jest --ci",
  "protect": ["tests/**", "__tests__/**", "jest.config.js", ".github/workflows/**"],
  "census": false
}
```

## Keep the check itself out of the change's reach

TheUstad reads its policy and tests from the base commit. The workflow file
that runs TheUstad is still part of the pull request, though, and on
`pull_request` events GitHub runs the pull request's own copy of it.

- An edit to `.github/workflows/**` is reported as `TAMPERED` while the check
  still runs. On a pull request the action compares against the base commit
  GitHub reports, ignoring the `base` input. It judges only the revision
  GitHub reports, the merge commit or the pull request's head, with tracked
  files unchanged and no untracked files beyond those `.gitignore` names, so
  the workflow cannot point either side of the comparison somewhere else. On
  a push or any other event the same holds for the commit the run is for,
  `github.sha`. It reads the checkout through a git directory of its own,
  because flags and settings a step writes into `.git` can hide a change from
  `git status`, and it drops the `GIT_*` variables a step can export to the
  rest of the job, which can do the same.
- Steps before the check that run the pull request's own code, such as
  `pip install -e .` or a setup script, can still change what the tests see,
  in ignored files or outside the checkout. That is the same boundary as the
  census: code under test runs with the job's permissions.
- That holds only while the pull request's copy still runs this action. One
  that replaces the step, or points `uses:` somewhere else, decides its own
  result, which is why `.github/` belongs under `CODEOWNERS` below.
- A pull request that **deletes** the step never runs TheUstad at all. A
  required status check then never reports, so the pull request cannot merge.
  That is why the check must be required.
- To stop the workflow from being edited in the first place, add
  `.github/` and `.theustad.json` to `CODEOWNERS` with required code-owner
  review, or run the check as an organisation ruleset's required workflow.
- Use `pull_request`, never `pull_request_target`, for this job. The check
  runs the pull request's code, and `pull_request_target` would give that code
  your secrets and a write token.

## Run it locally

```bash
python theustad.py ci --base origin/main
```

It compares `HEAD` with its merge base and restores the base commit's tests
while the tests run. Afterwards it puts every protected file back exactly as
it was, untracked files included. In a disposable checkout, add `--ephemeral`
to skip that step. `--json FILE` and `--summary FILE` write the same results
the action uses.

## What it does not do

- **It runs the change's code.** Installing and testing a pull request
  executes it, as any CI does. That code can forge the census report, exactly
  as in the other modes (see [What the census does not defend
  against](../README.md#what-the-census-does-not-defend-against)). Run the job
  without secrets.
- **The census baseline runs in your job's environment.** It runs the base
  commit's tests in a separate worktree, using whatever your install step put
  on the path. If that install is an editable install of the pull request's
  own checkout (`pip install -e .` with a `src/` layout), the baseline imports
  the pull request's code and is weaker for it. A plain `pip install .`, a
  flat layout, or `--no-census` avoids that.
- **`pyproject.toml`, `setup.cfg` and `tox.ini` are protected** by default,
  because each can carry pytest configuration. A pull request that only
  changes dependencies there is still reported as `TAMPERED`. If that is
  normal for your project, move the pytest configuration to `pytest.ini` and
  set `protect` in `.theustad.json`.
- **New tests are not run by this check.** They are excluded so they cannot
  influence the existing ones; your ordinary CI still runs them.
- **Tests that write into protected paths while running** (snapshot tests
  writing new snapshots, for example) are reported as tampering. Run them in
  their CI mode.
- Protected files stored as symlinks or through Git LFS are not supported.
