# pySTEMTC V1 — Round-1 expert review request

**Date**: 2026-09-20
**Branch**: `main`
**HEAD**: `c5114b7` (FINAL-B post-review of FINAL-A `8d160a7`)
**Round status**: FINAL-A + FINAL-B both closed.  Algorithm dev **FROZEN**.
**Review zip**: see below (no per-file dump for the experts).

## TL;DR

pySTEMTC V1 implements the Java STEM v1.3.14 M1 chain + STEM clustering
method (M2) with **byte-exact equivalence** to the Java reference on the
R1 Brain-trajectory testdata (1635 retained genes / 50 profiles / 7
significant / IDs {10,16,17,39,41,44,49}).  CLI surface frozen, M5
warning frozen, 281 tests green, wheel builds, clean-install smoke from
`/c/tmp` (outside the repo) is byte-exact with the canonical output.

**Frozen words (FINAL-B acceptance)**:

```
pySTEMTC algorithm development: FROZEN
Ready for real time-course datasets: YES
```

## What I want from the expert team

Three things, prioritized:

1. **P0 sanity check on the Java byte-exact comparison** — confirm that
   the 90079-byte genetable I produced in Python and the 90079-byte
   Java genetable match row-for-row on R1.  This is the load-bearing
   claim of V1; everything else is downstream of it.
2. **P1 review of the CLI design** — frozen surface
   `pystemtc run|batch`, exit codes 0/1/2, relative-path rule, batch
   continues on failure.  Is anything wrong, surprising, or missing?
3. **P2 review of the M5 warning + frozen text** — is the wording
   correct, is once-per-analysis the right cadence, should it be
   category `UserWarning`?

## What is settled and not up for debate

- K-means is `NotImplementedError` (frozen V1 scope).
- GO / two-condition comparison / GUI / R2 / R3 are out of V1.
- Writer API: `encoding=None, newline=None` defaults (platform
  default); pass `encoding="gbk", newline="\r\n"` for C2 byte-exact.
- No performance pass/fail threshold (V1 has no perf gate).

## Concrete open issues where I want the experts' opinion

### A. The Java vs Python "t0 reference" divergence

This is the only thing that genuinely surprised me during FINAL-A.

- The R1 main.txt (1999 genes × 7 Brain columns in biological order)
  treats column 0 (E10.5) as t0 — biologically correct.
- A previous Java run (the v1 R1 output at
  `D:/stem/benchmark_data/R1/out/R1_genetable.txt`, kept as a
  reference) used **8W as t0** because the file at that time had 8W
  in column 0.  The Java STEM output ordering matches its column
  ordering: the file's first data column is t0.
- When I re-ran Java STEM v1.3.14 on the v2 (biological-order) main.txt
  via `java -cp stem.jar edu.cmu.cs.sb.stem.ST -b <cfg> <out>`, Java
  correctly used E10.5 as t0 and produced a 90079-byte genetable
  **byte-exact** with Python's output.

So the algorithm itself agrees; the question is whether the user
community expects STEM v1.3.14's "first column is t0" convention or
"earliest biological time-point is t0" convention.  My implementation
follows the file-order convention (which is what Java STEM v1.3.14
also does).  No action needed unless the experts see a real-world
dataset where this would bite.

### B. Path handling on Windows + MSYS bash

- `Path.write_text("\n".join(...))` silently translates `\n` to
  `\r\n` on Windows, which changed `analysis_input_sha256` by exactly
  one byte per line.  Fixed by `Path.write_bytes(....encode("utf-8"))`
  in `verification/derive_r1_brain7.py`.  No runtime impact (the
  runtime reader is line-orientation-agnostic) but the manifest
  anchor required exact bytes.
- The CLI's `--newline` argument takes a string; if a user passes
  `--newline \r\n` from Git Bash, the escape is eaten by the shell.
  Documented in `README.md` (use `$'\r\n'`) but worth flagging.

### C. `Spot_IDs_included_in_the_data_file=false` semantics

Java STEM v1.3.14 with this flag set to `false` treats the file's
data columns as the time course; there is **no** synthetic "0"
column prepended at write time.  The reader in `pystemtc.dataio`
matches this.  Profile IDs are 0-indexed positions in the model
candidate list (after `compact_profiles2` sorting).

### D. JSON schema-v2 in `to_dict()`

`GeneAssignment.values` carries None for NaN/±Inf (encoded as
`value_states`), and `present` carries the pma mask.  Both are
preserved; no information is collapsed.  This is round-7.1 territory
and not changing in V1.

### E. Out-of-scope things the experts might still ask about

- K-means: explicitly `NotImplementedError` (raises at `_analyze()`).
- V1.1 plan: K-means with `Random(2211)` + reservoir-sampling
  restart replica (mentioned in `engine.py` error message).
- Gene Annotation / Cross-Reference / GO / Interface sections of
  `defaults.txt`: silently ignored (key not in `_NORMALIZE_MAP` /
  parse dispatch).

## Things that are NOT issues (already verified)

| claim | evidence |
|---|---|
| Python API == Python CLI byte-exact | `verification/derive_r1_brain7.py` runs both and compares `read_bytes()` |
| Python API == Java STEM v1.3.14 byte-exact | `java_R1_brain_trajectory_*.txt` in `final_acceptance/R1_brain_trajectory/` |
| Source TSV hash matches manifest | `9e6dba16d1dcfcb4ea39226066e7c3bc53c0175888122134e8357285cef54514` |
| Derived main.txt hash matches manifest | `ef8e6ae3915c50bcef518d737b915e9e36d83bb2bb02c59cf643b27a105a45ac` |
| 1635 retained genes | `len(api_g.splitlines())-1 == 1635` |
| 50 profiles / 7 significant / IDs match | re-counted; see anchor table in `FINAL_ALGORITHM_ACCEPTANCE.md` |
| 281 tests pass | `pytest_full.log` (real number, not hardcoded) |
| Wheel installs + CLI runs from outside repo | `/c/tmp/out/R1_genetable.txt` byte-exact with canonical |
| M5 warning fires once, correct category | 6 tests in `tests/test_m5_warning.py` |

## Next steps (my proposal, for expert input)

The user has frozen algorithm dev after FINAL-B.  My recommended
post-V1 actions, in priority order:

1. **P0**: expert review of the byte-exact claim (see A above).
2. **P1**: if review is clean, tag `v1.0.0` and publish the wheel to
   a private index for the user's internal team.
3. **P2**: write a short `docs/MIGRATION_FROM_JAVA_STEM.md` so
   Java users can adopt pySTEMTC without reading the source.  This
   is the single most impactful documentation task.
4. **P3**: V1.1 = K-means.  Plan only, no implementation, until V1
   ships.
5. **P4**: `docs/V1.1_DESIGN.md` for the K-means + reservoir
   sampling replica.  Out of scope for this review.

## What I'm explicitly NOT asking the experts to do

- Re-read 281 tests.  The pytest log is in the zip; the per-suite
  counts are in `FINAL_ALGORITHM_ACCEPTANCE.md`.
- Re-derive the Java outputs.  The Java invocation pattern is in
  `verification/derive_r1_brain7.py` (`-cp stem.jar edu.cmu.cs.sb.stem.ST -b <cfg> <out>`).
- Re-run the clean-install smoke.  The byte-exact comparison is in
  the README and the zip carries the canonical output as the
  reference.
- Audit `engine.py` or `result.py` for performance — V1 has no
  perf gate.
