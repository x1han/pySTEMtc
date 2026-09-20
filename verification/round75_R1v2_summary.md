# Real-data benchmark summary -- R1_brain_trajectory

- generated: pySTEMTC 0.1.0 @ 896f201
- Python: 3.14.3, NumPy 2.4.6, pandas 3.0.3
- Java: java version "1.8.0_451" (binary: `C:\Program Files (x86)\Common Files\Oracle\Java\java8path\java.EXE`)
- stem.jar: `D:\stem\stem.jar` (sha256 `eb17762eb9f31296...`)
- platform: Windows-11-10.0.26200-SP0
- CPU: Intel64 Family 6 Model 183 Stepping 1, GenuineIntel (28 logical), RAM 31.7 GiB

> **Performance vs Compatibility**: The first-column judgment is **assignment_exact** (Java vs PySTEMTC profile_id order on every retained gene). Performance numbers (end-to-end wall, peak RSS) are descriptive, NOT release-blocking. The Py/Java end-to-end ratio above 1 is *not* a release gate -- it would be *fair* to compare now because both languages use the same subprocess-isolated measurement protocol.

## Dataset profile (round-7.5 expanded schema)

| dataset_id | input_rows | unique_genes | dup_rows | T | reps |
|---|---|---|---|---|---|
| R1_brain_trajectory | 1999 | 1999 | 0 | 7 | 0 |

| raw_missing | zero | nonpositive (= effective missing under log) | value range | value_median |
|---|---|---|---|---|
| 0.0000 | 0.1064 | 0.1064 | [0.0, 5641.1103] | 19.8249 |

### Provenance (sha256)

- input_sha256 (from manifest.description): `(not provided)`
- derivation_sha256 (main.txt on disk): `ef8e6ae3915c50bcef518d737b915e9e36d83bb2bb02c59cf643b27a105a45ac`
- derivation_description: (none)

## assignment_exact (round-7.5; ordered list, NOT set)

- Java retained: 1635
- Py retained:   1635
- Common:        1635
- Java-only:     0
- Py-only:       0
- Mismatches in common (ordered-list !=): 0
- **assignment_exact: PASS**

## Compatibility C1

> **NOT YET ASSESSED** -- the writer (``STEMResult.write_java_tables``) is implemented in a future round; before then, this benchmark cannot produce a Python genetable / profiletable to byte-compare against the Java oracle. See docs/03 §1.10 (round-7.3 writer contract sweep).

## Main table -- end-to-end wall (parent subprocess timer, cross-language-comparable)

| Language | wall median | wall min | wall max | RSS MiB median | exit_code |
|---|---|---|---|---|---|
| Python | 2.782 | 2.777 | 2.801 | 85.7 | [0] |
| Java | 2.534 | 2.483 | 2.634 | 13.6 | [0] |

Py/Java end-to-end ratio (median, descriptive): **1.10x**

## PySTEMTC core_wall (engine.fit() internal; for Py optimization analysis only)

| core_wall median | core_wall min | core_wall max |
|---|---|---|
| 2.181 | 2.177 | 2.189 |

## PySTEMTC stage timings (median, seconds)

| input_read | normalize_filter | profile_generation | assignment | permutation | significance | clustering |
|---|---|---|---|---|---|---||
| 0.014 | 0.015 | 0.365 | 0.094 | 1.672 | 0.017 | 0.000 |
