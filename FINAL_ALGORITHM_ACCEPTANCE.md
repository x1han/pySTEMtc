# FINAL_ALGORITHM_ACCEPTANCE

**Date**: 2026-09-21
**HEAD**: see `verification/git_state.txt` (FINAL-B hotfix commit, post expert-review)
**Branch**: `main`
**Final**: pySTEMTC algorithm development is **FROZEN**.
**Ready for real time-course datasets**: **YES**.

This document is the formal acceptance of pySTEMTC V1 against the Java
STEM v1.3.14 byte-exact oracle.  All gates from the round-1 spec are
green; nothing new is permitted beyond this point.

## Frozen words

```
pySTEMTC algorithm development: FROZEN
Ready for real time-course datasets: YES
```

## Status against the round-1 spec gates

| gate | status |
|---|---|
| Python API repeat wiring | **PASS** |
| CLI no-repeat | **PASS** |
| CLI different-period repeat | **PASS** (byte-exact vs Java c01 oracle) |
| CLI same-period repeat | **PASS** (byte-exact vs Java c07 oracle) |
| R1 testdata (Brain 7) | **PASS** (byte-exact vs Java R1 oracle) |
| Writer C1 (decoded-exact) | **PASS** |
| Writer C2 (byte-exact) | **PASS** |
| Wheel clean-install | **PASS** (`/c/tmp/fin_b_smoke` byte-exact with Java) |
| Full pytest | **PASS** (285 passed in 481.49s; real number) |
| Git clean | **PASS** (no untracked files) |

## FINAL-B hotfix (post expert-review)

The expert team reproduced a **P0-DELIVERY bug**: the CLI silently
ignored `Repeat_Data_Files`.  Three CLI runs (c01, c07, c08) produced
identical SHA256 for both tables.  Root cause: `cli._run_one_config`
called `stem_engine.fit(data_file)` without `replicates=`.

Fix:

```python
# src/pystemtc/cli.py::_run_one_config
result = stem_engine.fit(
    data_file,
    replicates=list(config.repeat_files) or None,
)
```

This was the only P0 the experts surfaced; algorithm core and R1
Brain7 path were not touched.

## M5 contract cleanup

The M5 warning text was previously a duplicated string in two places
(engine + tests, fragment-matched).  The hotfix promotes it to a
single source of truth:

```python
# src/pystemtc/engine.py
M5_WARNING = (
    "normalize='none_add0' with permute_t0=True permutes the "
    "synthetic zero baseline together with observed time points, "
    "matching legacy STEM v1.3.14 behavior. Interpret "
    "permutation-based significance with caution."
)
```

`tests/test_m5_warning.py` now asserts full equality:

```python
assert str(w.message) == M5_WARNING
```

Drift between the two halves is now caught at test time.

## A1 — Reproduction baseline

- HEAD at start of FINAL-A: `c753afa` (clean working tree).
- Python: 3.14.3 (C:\Python314\python.exe).
- numpy 2.4.6, pandas 3.0.3.
- Java: JRE 1.8.0_451 (STEM v1.3.14 reference).

## A2 — Writer closeout

- `STEMResult.write_java_tables(encoding=None, newline=None)` defaults.
  `None` = platform default.  Pass `encoding="gbk", newline="\r\n"` for
  C2 byte-exact against the Java golden oracles.
- Last column always rendered (Java ST.java:3033 quirk).
- Interior cell empty when `present[j] == False` (priority over NaN
  payload).  Test: `test_genetable_cell_missing_interior_overrides_nan_payload`.
- Single source of truth: `pystemtc.javaformat.format_java_double`
  (two-path dispatch).
- W1 = 57, W2 = 30, W3 = 30 (all green).

## A3 — Manifest + summary banner

- R1 manifest fields renamed:
  - `input_sha256`      → `source_sha256`
  - `derivation_sha256` → `analysis_input_sha256`
- Summary banner rewritten:
  - "equivalent-workload process-level wall"
  - "R1 observed Py/Java ratio is descriptive only.  Its source is
    not characterized.  It is NOT a release gate.  V1 has no
    performance pass/fail threshold."
  - PROVISIONAL / mechanism-attribution language removed.

## A4 — CLI

- New: `src/pystemtc/cli.py` + `[project.scripts] pystemtc = "pystemtc.cli:main"`.
- Frozen surface:
  - `pystemtc run    --config <defaults.txt> --output <dir>`
  - `pystemtc batch  --config-dir <dir>  --output <dir>`
- Frozen exit codes: 0 = success, 1 = analysis / config / I/O failure,
  2 = CLI usage error.
- Relative path rule: `Data_File` / `Repeat_Data_Files` resolved
  against the config file's directory, not CWD.
- Batch mode: continues on per-config failure; exit 1 if any failed.
- Repeat wiring: passes `replicates=list(config.repeat_files) or None`
  to `engine.fit()`.  `repeat_mode` is passed to `STEM()` constructor.
- 14 tests in `tests/test_cli.py` (run=0/1/2, batch=0/1,
  batch-continues-on-failure, relative-path-resolved-against-config,
  **CLI c01 different-period byte-exact vs Java oracle**,
  **CLI c07 same-period byte-exact vs Java oracle**,
  c01/c07/c08 outputs distinct).

## A5 — M5 warning

- Emits **once per analysis** when `normalize='none_add0'` AND
  `permute_t0=True`.
- Frozen text lives in `pystemtc.engine.M5_WARNING`.
- Category: `UserWarning`.
- 7 tests in `tests/test_m5_warning.py` (fires / silent on each axis,
  exactly-once, UserWarning category, **text equals frozen constant**).

## A6 / A7 — Real testdata canonical run

- Source: `D:/stem/testdata/stem.testdata.tsv`
  - `source_sha256 = 9e6dba16d1dcfcb4ea39226066e7c3bc53c0175888122134e8357285cef54514`
- Derived analysis main.txt: `final_acceptance/R1_brain_trajectory/main.txt`
  - `analysis_input_sha256 = ef8e6ae3915c50bcef518d737b915e9e36d83bb2bb02c59cf643b27a105a45ac`
- **Anchor check**:

| metric | expected | actual |
|---|---|---|
| input rows | 1999 | **1999** |
| retained genes | 1635 | **1635** |
| model profiles | 50 | **50** |
| significant profiles | 7 | **7** |
| significant profile ids | {10,16,17,39,41,44,49} | **{10,16,17,39,41,44,49}** |

- **Byte-exact (C2)**:
  - Python API == Python CLI: byte-exact
  - Python API == Java STEM v1.3.14: byte-exact (genetable 90 079 B,
    profiletable 3 364 B)

## A8 — Full pytest

**285 passed in 481.49s** (FINAL-B hotfix; FINAL-A was 281).

| suite | passed |
|---|---|
| `test_units.py` | 35 |
| `test_units_m2.py` | 20 |
| `test_writer.py` | 57 |
| `test_cli.py` | **14** (was 11; +3 = c01, c07, distinctness) |
| `test_m5_warning.py` | **7** (was 6; +1 = constant-equality) |
| `test_integration_fixture.py` | 17 |
| `test_golden.py` | 42 |
| `test_golden_branches.py` | 6 |
| `test_writer_golden_c1.py` | 30 |
| `test_writer_golden_c2.py` | 30 |
| `test_float_discipline.py` | 1 |
| `test_result_schema.py` | 22 |
| `test_rng.py` | 4 |
| **TOTAL** | **285** |

9 warnings are all the M5 warning firing on the `c04_add0` and
`headers_custom` golden cases (intentional M5 combination exercised
as a byte-exact oracle for that branch).

## A9 — FINAL-A + FINAL-B + FIN-B hotfix commits

- `8d160a7` FINAL-A: writer defaults, CLI, M5 warning, R1 anchor + Java byte-exact, 281 green.
- `c5114b7` FINAL-B: README, FINAL_ALGORITHM_ACCEPTANCE, refreshed git_state.
- `70d0520` docs(round-FINAL): expert review request for V1 byte-exact + CLI + M5.
- The FIN-B hotfix commit (this round) closes the P0 wiring bug.

## Clean-install smoke evidence (FIN-B + release closeout)

Captured to `final_acceptance/R1_brain_trajectory/_smoke/clean_install_smoke.log`:

```
wheel: dist/pystemtc-1.0.0-py3-none-any.whl
  size = 63 628 B
  sha256 = 58aa228136532a43ac952a25643f89ca9bc93e6160db6d264ebfb023e69ccb9d

fresh venv: /tmp/pystemtc_smoke_venv
  pip install pystemtc-1.0.0-py3-none-any.whl numpy pandas
  pystemtc run c01  (different-period repeat) -> exit 0
  pystemtc run c07  (same-period repeat)      -> exit 0
  pystemtc run R1   (Brain 7, no repeat)      -> exit 0

byte-exact vs Java oracle (from outside repo at /c/tmp/fin_b_smoke):
  c01 different-period genetable   : smoke == java  (102 121 B == 102 121 B)
  c01 different-period profiletable : smoke == java  (   2 311 B ==   2 311 B)
  c07 same-period genetable         : smoke == java  (138 125 B == 138 125 B)
  c07 same-period profiletable      : smoke == java  (   2 335 B ==   2 335 B)
  R1  Brain 7 genetable             : smoke == java  ( 90 079 B ==  90 079 B)
  R1  Brain 7 profiletable          : smoke == java  (   3 364 B ==   3 364 B)
```

Wheel is also preserved at `final_acceptance/R1_brain_trajectory/_wheel/pystemtc-1.0.0-py3-none-any.whl`
for delivery inspection.

## Release closeout (v1.0.0 prep)

- Package version: `1.0.0` (was `0.1.0`; sync with `pyproject.toml`,
  `src/pystemtc/__init__.py:__version__`, and the wheel filename).
- M5 frozen literal restored without the FIN-B `M5: ` prefix:
  ```
  normalize='none_add0' with permute_t0=True permutes the synthetic zero
  baseline together with observed time points, matching legacy STEM
  v1.3.14 behavior. Interpret permutation-based significance with caution.
  ```
  See `pystemtc.engine.M5_WARNING` and
  `tests/test_m5_warning.py::test_m5_warning_text_is_the_frozen_constant`.
- `.gitignore` extended with `benchmarks/results/` (timestamp-named
  runtime outputs).  `git status --porcelain` is empty after the
  release-closeout commit.

## Out of V1 scope (will not be added)

- K-means clustering method (`NotImplementedError` at `_analyze()`).
- Two-condition comparison / GO / KEGG enrichment.
- GUI / interactive display.
- R2 / R3 (future).

---

**Acceptance**: pySTEMTC V1 algorithm development is **FROZEN** as of
the FIN-B hotfix commit.  Ready for real time-course datasets: **YES**.
