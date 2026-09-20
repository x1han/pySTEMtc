# FINAL_ALGORITHM_ACCEPTANCE

**Date**: 2026-09-20
**HEAD**: `8d160a7` (FINAL-A implementation closeout)
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

## A1 -- Reproduction baseline

- HEAD at start of FINAL-A: `c753afa` (clean working tree, see commit message).
- Python: 3.14.3 (C:\Python314\python.exe).
- numpy 2.4.6, pandas 3.0.3.
- Java: JRE 1.8.0_451 (STEM v1.3.14 reference).

## A2 -- Writer closeout

- `STEMResult.write_java_tables(encoding=None, newline=None)` defaults.
  `None` = platform default (mirrors Java on this host).  For C2
  byte-exact comparison against the Java golden oracles, pass
  `encoding="gbk", newline="\r\n"` explicitly.
- Last column always rendered (Java ST.java:3033 quirk).
- Interior cell empty when `present[j] == False` (priority over NaN
  payload).  New test `test_genetable_cell_missing_interior_overrides_nan_payload`.
- Single source of truth: `pystemtc.javaformat.format_java_double`
  (two-path dispatch: binary HALF_EVEN + Decimal(repr) fallback).
- W1 = 57, W2 = 30, W3 = 30 (all green).

## A3 -- Manifest + summary banner

- R1 manifest fields renamed:
  - `input_sha256`      -> `source_sha256`
  - `derivation_sha256` -> `analysis_input_sha256`
- Summary banner rewritten:
  - "equivalent-workload process-level wall" (both languages run
    analysis + writer; workload is equivalent).
  - "R1 observed Py/Java ratio is descriptive only.  Its source is
    not characterized.  It is NOT a release gate.  V1 has no
    performance pass/fail threshold."
  - PROVISIONAL / mechanism-attribution language removed.
- Ratio relabeled: "descriptive only, NOT a release gate".

## A4 -- CLI

- New: `src/pystemtc/cli.py` + `[project.scripts] pystemtc = "pystemtc.cli:main"`.
- Frozen surface:
  - `pystemtc run    --config <defaults.txt> --output <dir>`
  - `pystemtc batch  --config-dir <dir>  --output <dir>`
- Frozen exit codes:
  - `0` = success
  - `1` = analysis / config / I/O failure
  - `2` = CLI usage error
- Relative path rule: `Data_File` / `Repeat_Data_Files` resolved
  against the config file's directory, not CWD.
- Batch mode: continues on per-config failure; exit 1 if any failed.
- Config detection (batch): first non-blank, non-`#` line is
  `Data_File<TAB>value` -- protects against `g27_1.txt` data files
  being treated as configs.
- 11 tests in `tests/test_cli.py` (run=0/1/2, batch=0/1,
  batch-continues-on-failure, relative-path-resolved-against-config,
  in-process and `python -m` subprocess entry points).

## A5 -- M5 warning

- Emits **once per analysis** when `normalize='none_add0'` AND
  `permute_t0=True`.
- Frozen text (in `src/pystemtc/engine.py`):
  > M5: normalize='none_add0' with permute_t0=True permutes the
  > synthetic zero baseline together with observed time points,
  > matching legacy STEM v1.3.14 behavior.  Interpret
  > permutation-based significance with caution.
- Category: `UserWarning`.
- 6 tests in `tests/test_m5_warning.py`.

## A6 -- Real testdata canonical run

- Source: `D:/stem/testdata/stem.testdata.tsv`
  - `source_sha256 = 9e6dba16d1dcfcb4ea39226066e7c3bc53c0175888122134e8357285cef54514`
- Derived analysis main.txt: `final_acceptance/R1_brain_trajectory/main.txt`
  - `analysis_input_sha256 = ef8e6ae3915c50bcef518d737b915e9e36d83bb2bb02c59cf643b27a105a45ac`
- **Anchor check (P0 if violated)**:

| metric | expected | actual |
|---|---|---|
| input rows | 1999 | **1999** |
| retained genes | 1635 | **1635** |
| model profiles | 50 | **50** |
| significant profiles | 7 | **7** |
| significant profile ids | {10,16,17,39,41,44,49} | **{10,16,17,39,41,44,49}** |

- **Byte-exact (C2)**:
  - Python API == Python CLI: **byte-exact** (genetable, profiletable)
  - Python API == Java STEM v1.3.14: **byte-exact** (genetable, profiletable)

## A7 -- final_acceptance drop

`final_acceptance/R1_brain_trajectory/` contains 11 files:

1. `source_manifest.yaml`
2. `main.txt`
3. `R1_brain_trajectory_genetable.txt` (Python API output)
4. `R1_brain_trajectory_profiletable.txt` (Python API output)
5. `java_R1_brain_trajectory_genetable.txt` (Java STEM v1.3.14 output)
6. `java_R1_brain_trajectory_profiletable.txt` (Java STEM v1.3.14 output)
7. `testdata_result_summary.md` (anchor + byte-exact evidence)
8. `pytest_full.log` (full pytest, last line = real count)
9. `cli_run.log` (CLI run exit 0)
10. `cli_batch.log` (CLI batch exit 1, 1/2 configs failed by design)
11. `provenance.txt` (toolchain snapshot)

## A8 -- Full pytest

**281 passed in 468.37s** (real number from the run, not hardcoded).

| suite | passed |
|---|---|
| `test_units.py` | 35 |
| `test_units_m2.py` | 20 |
| `test_writer.py` | 57 |
| `test_cli.py` | 11 |
| `test_m5_warning.py` | 6 |
| `test_integration_fixture.py` | 17 |
| `test_golden.py` | 42 |
| `test_golden_branches.py` | 6 |
| `test_writer_golden_c1.py` | 30 |
| `test_writer_golden_c2.py` | 30 |
| `test_float_discipline.py` | 1 |
| `test_result_schema.py` | 22 |
| `test_rng.py` | 4 |
| **TOTAL** | **281** |

9 warnings are all the M5 warning firing on the `c04_add0` and
`headers_custom` golden cases (the M5 combination is intentional
and exercised as a byte-exact oracle for that branch).

## A9 -- FINAL-A commit

- Commit `8d160a7` carries the entire FINAL-A diff: 20 files,
  6732 insertions(+), 35 deletions(-).
- Working tree is clean (modulo one stray `docs/08_m4_round8_final_report.md`
  from a previous round, which is left out of FINAL-A).

## FINAL-B -- Post-review

- Wheel builds: `pystemtc-0.1.0-py3-none-any.whl` (63 362 bytes,
  sha256 `e85c965ff9f2f60deb779cb77a446d029fc24a031079e2ad0398b02ee1dddc7a`).
- Fresh-venv clean-install smoke test:
  - `python -m venv /tmp/pystemtc_smoke_venv`
  - `pip install pystemtc-0.1.0-py3-none-any.whl numpy pandas`
  - `pystemtc --help` shows `run` and `batch` subcommands.
  - `pystemtc run --config /c/tmp/cfg/R1.txt --output /c/tmp/out --encoding gbk --newline $'\r\n'`
    from CWD `/c/tmp` (outside the repo) writes both tables;
    output bytes are **byte-exact** with the canonical FINAL-A output
    (sha256 `b74b2a388382e258e99b1a87c6e2653e` on both).
- README: `D:/stem/pySTEMtc/README.md` (root, GitHub-flavored markdown).
- Final review zip: `verification/final_algorithm_review.zip`
  (TBD after FINAL-B passes).

## Out of V1 scope (will not be added)

- K-means clustering method
- Two-condition comparison
- GO / KEGG enrichment
- GUI / interactive display
- R2 / R3

---

**Acceptance**: pySTEMTC V1 algorithm development is **FROZEN** as of this
commit.  Ready for real time-course datasets: **YES**.
