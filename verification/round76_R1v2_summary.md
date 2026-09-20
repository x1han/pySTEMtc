# Real-data benchmark summary -- R1_brain_trajectory

- generated: pySTEMTC 0.1.0 @ fa28768
- Python: 3.14.3, NumPy 2.4.6, pandas 3.0.3
- Java: java version "1.8.0_451" (binary: `C:\Program Files (x86)\Common Files\Oracle\Java\java8path\java.EXE`)
- stem.jar: `D:\stem\stem.jar` (sha256 `eb17762eb9f31296...`)
- platform: Windows-11-10.0.26200-SP0
- CPU: Intel64 Family 6 Model 183 Stepping 1, GenuineIntel (28 logical), RAM 31.7 GiB

> **Performance vs Compatibility**: First-column judgment is **assignment_exact** (Java vs PySTEMTC profile_id order on every retained gene). Performance numbers (end-to-end wall, peak RSS) are descriptive, NOT release-blocking.

> **Py/Java e2e ratio is PROVISIONAL (round-7.6 ruling)**: Java's fresh JVM runs the full batch (analysis + genetable + profiletable writes). PySTEMTC's fresh subprocess currently runs analysis only -- the writer (`STEMResult.write_java_tables`) is **not yet** implemented. Once writer is integrated into the Python worker path, the ratio becomes the official cross-language baseline.

## Dataset profile (round-7.6 schema: smaller is better)

| dataset_id | input_rows | unique_genes | dup_rows | T | reps |
|---|---|---|---|---|---|
| R1_brain_trajectory | 1999 | 1999 | 0 | 7 | 0 |

| raw_missing | zero | nonpositive (raw, NOT pma missing) | value range | value_median |
|---|---|---|---|---|
| 0.0000 | 0.1064 | 0.1064 | [0.0, 5641.1103] | 19.8249 |

> **Round-7.6 P1-BENCH semantic fix**: `nonpositive_rate` is the share of raw cells with `value <= 0`. Under log mode these cells produce **non-finite payloads** (`-Inf` for `v == 0`, `NaN` for `v < 0`) per `_log_java` in `src/pystemtc/normalize.py:20-26`. They do **NOT** automatically become pma-missing -- pma is set to 0 only when t0 itself was raw-missing (row-level cascade). We do not auto-compute an `effective_missing_rate` here because that would require running normalization and counting pma zeros, which is the algorithm's responsibility (deferred until the writer round adds pma instrumentation).

### Provenance (sha256, round-7.6 naming)

- analysis_input_sha256 (main.txt on disk, what the engine reads): `ef8e6ae3915c50bcef518d737b915e9e36d83bb2bb02c59cf643b27a105a45ac`
- source_sha256 (upstream tsv from manifest.description): `9e6dba16d1dcfcb4ea39226066e7c3bc53c0175888122134e8357285cef54514`
- derivation_description: Derived from D:/stem/testdata/stem.testdata.tsv (1999 ENSG-Mus-musculus genes × 60 multi-stage tissue columns).
R1 v1: Brain trajectory T=7 in source order (8W first -- wrong, 8W is adult 8 weeks).
R1 v2 (round-7.5 P1-4): Brain trajectory T=7 in biological developmental order:
  E10.5_Brain, E12.5_Brain, E14.5_Brain, E16.5_Brain,
  P0_Brain, P21_Brain, 8W_Brain (adult).
Dropped gene_id; kept gene_name as the ID column (spot_included=false).


> The `analysis_input_sha256` is what makes the benchmark result reproducible; `source_sha256` belongs to provenance one level up.


## assignment_exact (round-7.5; ordered list, NOT set)

- Java retained: 1635
- Py retained:   1635
- Common:        1635
- Java-only:     0
- Py-only:       0
- Mismatches in common (ordered-list !=): 0
- **assignment_exact: PASS**

## Determinism sanity (round-7.6 P2)

Both languages should be deterministic on fixed input + seed; if any formal run produces a different profile_ids set, that's a real bug (silently broken run).

- Python: PASS (formal runs 3)
- Java:   PASS (formal runs 3)

## Compatibility C1

> **NOT YET ASSESSED** -- the writer (``STEMResult.write_java_tables``) is implemented in a future round; before then, this benchmark cannot produce a Python genetable / profiletable to byte-compare against the Java oracle. See docs/03 §1.10 (round-7.3 writer contract sweep).

## Main table -- end-to-end wall (parent subprocess timer, cross-language-comparable)

| Language | wall median | wall min | wall max | RSS MiB median | exit_code |
|---|---|---|---|---|---|
| Python | 2.696 | 2.647 | 2.794 | 85.6 | [0] |
| Java | 2.560 | 2.512 | 2.596 | 13.7 | [0] |

Py/Java end-to-end ratio (median, descriptive): **1.05x**

## PySTEMTC core_wall (engine.fit() internal; for Py optimization analysis only)

| core_wall median | core_wall min | core_wall max |
|---|---|---|
| 2.099 | 2.062 | 2.170 |

## PySTEMTC stage timings (median, seconds)

| input_read | normalize_filter | profile_generation | assignment | permutation | significance | clustering |
|---|---|---|---|---|---|---||
| 0.014 | 0.015 | 0.346 | 0.092 | 1.612 | 0.016 | 0.000 |
