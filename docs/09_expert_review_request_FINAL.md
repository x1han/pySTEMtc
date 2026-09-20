# pySTEMTC V1 — Round-1 expert review request

**Date**: 2026-09-21
**Branch**: `main`
**HEAD**: see `verification/git_state.txt` (FIN-B hotfix)
**Round status**: FINAL-A + FINAL-B + FIN-B hotfix closed.
Algorithm dev **FROZEN**.
**Review zip**: see `verification/final_FIN_B_review_<TS>.zip`
(no per-file dump for the experts).

## TL;DR

pySTEMTC V1 implements the Java STEM v1.3.14 M1 chain + STEM clustering
method (M2) with **byte-exact equivalence** to the Java reference on
three independent datasets:

- **R1 Brain-trajectory** (1999 genes × 7 Brain time points): byte-exact
- **c01 guillemin core** (different-period repeat): byte-exact
- **c07 same-period**: byte-exact

CLI surface frozen, M5 warning frozen via single source of truth,
285 tests green, wheel builds, clean-install smoke from `/c/tmp/fin_b_smoke`
(outside the repo) is byte-exact with the Java oracles on all three
cases.  Git tree clean.

**Frozen words (FIN-B + release closeout)**:

```
pySTEMTC algorithm development: FROZEN
Ready for real time-course datasets: YES
Package version: 1.0.0
Tag: v1.0.0  (HELD until GitHub Win/Linux CI green)
```

## What changed since the first review request

The expert team's first review surfaced a **P0-DELIVERY wiring bug**:
`cli._run_one_config` called `engine.fit(data_file)` without
`replicates=`, silently dropping `Repeat_Data_Files`.  All three
released V1 CLI paths (c01, c07, c08) collapsed to the same SHA256.

This round (FIN-B hotfix) closes that bug:

| change | file | lines |
|---|---|---|
| Wire `replicates=list(config.repeat_files) or None` | `src/pystemtc/cli.py` | +2 / -1 |
| M5 frozen text -> module constant `M5_WARNING` | `src/pystemtc/engine.py` | +9 / -5 |
| Add c01/c07 CLI Java-oracle byte-exact tests | `tests/test_cli.py` | +180 |
| Add M5 text-equality test | `tests/test_m5_warning.py` | +18 / -8 |
| README Python API example now passes `replicates=` | `README.md` | +12 / -1 |

No algorithm changes.  No new features.  No refactor.

## Final acceptance gates

| gate | evidence |
|---|---|
| Python API repeat | API path unchanged from FINAL-A; covered by golden tests |
| CLI no-repeat (c08) | `tests/test_cli.py::test_cli_run_happy_path` + golden c08 byte-exact |
| CLI different-period (c01) | `tests/test_cli.py::test_cli_c01_different_period_repeat_matches_java_byte_exact` |
| CLI same-period (c07) | `tests/test_cli.py::test_cli_c07_same_period_repeat_matches_java_byte_exact` |
| R1 testdata | `verification/derive_r1_brain7.py` + `final_acceptance/R1_brain_trajectory/` |
| C1 (decoded-exact) | `tests/test_writer_golden_c1.py` (30/30) |
| C2 (byte-exact) | `tests/test_writer_golden_c2.py` (30/30) |
| Wheel clean-install | `final_acceptance/R1_brain_trajectory/_smoke/clean_install_smoke.log` |
| Full pytest | `verification/pytest_full_FIN_B.log` (285 passed in 481.49s) |
| Git clean | `git status` empty after the FIN-B hotfix commit |

## What I want from the expert team (this round, in priority order)

1. **P0 sanity check**: confirm the three byte-exact claims.
   - `final_acceptance/R1_brain_trajectory/R1_brain_trajectory_genetable.txt`
     vs `final_acceptance/R1_brain_trajectory/java_R1_brain_trajectory_genetable.txt`
     (both 90 079 B).
   - `final_acceptance/CLI_repeat_wiring/c01_different_period_genetable.txt`
     vs `final_acceptance/CLI_repeat_wiring/java_c01_genetable.txt`
     (both 102 121 B).
   - `final_acceptance/CLI_repeat_wiring/c07_same_period_genetable.txt`
     vs `final_acceptance/CLI_repeat_wiring/java_c07_genetable.txt`
     (both 138 125 B).
2. **P1 review of the M5 contract cleanup**: is the single-source-of-truth
   pattern acceptable, or do the experts prefer a different enforcement
   mechanism (e.g. an explicit `assert str(w.message) == M5_WARNING`
   inside the engine, not just the test)?
3. **P2 review of the release-readiness statement**: with the
   c01/c07 byte-exact coverage now in place, is V1 ready for the
   `v1.0.0` tag?

## What is settled and explicitly NOT up for debate

- K-means is `NotImplementedError` (frozen V1 scope).
- GO / two-condition comparison / GUI / R2 / R3 are out of V1.
- Writer API: `encoding=None, newline=None` defaults; pass
  `encoding="gbk", newline="\r\n"` for C2 byte-exact.
- No performance pass/fail threshold (V1 has no perf gate).

## Things that are NOT issues (already verified end-to-end)

- 285 tests pass (real number from this round, not hardcoded).
- Wheel installs and runs from `/c/tmp/fin_b_smoke` (outside repo) on
  all three byte-exact datasets.
- Git tree is clean (no untracked files after `docs/08_m4_round8_final_report.md`
  deletion).
- Wheel binary is preserved at
  `final_acceptance/R1_brain_trajectory/_wheel/pystemtc-0.1.0-py3-none-any.whl`
  and `dist/pystemtc-0.1.0-py3-none-any.whl`.
- Clean-install smoke log preserved at
  `final_acceptance/R1_brain_trajectory/_smoke/clean_install_smoke.log`.

## What I'm explicitly NOT asking the experts to do

- Re-run the 285 tests.  `verification/pytest_full_FIN_B.log` is in
  the review zip; per-suite counts are in `01_acceptance.md`.
- Re-run Java.  `05_derive_r1_brain7.py` has the invocation pattern.
- Re-run the clean-install smoke.  The byte-exact comparison is in
  the smoke log and the README.
- Audit engine.py / result.py for performance (V1 has no perf gate).

## Release closeout (v1.0.0 prep)

Four release blockers were surfaced after the FIN-B hotfix; all four
are now resolved in the release-closeout commit:

| blocker | resolution |
|---|---|
| Package version mismatch (`0.1.0` wheel, `1.0.0` tag would be wrong) | `pyproject.toml` + `__init__.py:__version__` bumped to `1.0.0`; wheel rebuilt as `pystemtc-1.0.0-py3-none-any.whl`. |
| M5 contract: FIN-B hotfix added an unauthorized `M5: ` prefix to the round-7.7 frozen literal | `M5_WARNING` reverted to the round-7.7 frozen text verbatim (no `M5: ` prefix); `test_m5_warning_text_is_the_frozen_constant` updated to match (still asserts full equality). |
| Working tree not actually clean (`benchmarks/results/` untracked dirs; `verification/git_state.txt` stale content) | `.gitignore` extended with `benchmarks/results/` (timestamp-named runtime outputs).  `git status --porcelain` empty after the release-closeout commit. |
| GitHub Win/Linux CI gate (release blocker) | Workflow already present (Win + Linux x Python 3.11/3.12/3.14, `pip install -e ".[dev]"`, `pytest -q`).  Release-closeout commit pushed; CI must be observed green before tagging `v1.0.0`. |

No algorithm changes in the release closeout.  No new features.
No refactor.
