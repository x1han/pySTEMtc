# R1 Brain trajectory -- testdata result summary (FINAL-A A6/A7)

**Dataset id**: R1_brain_trajectory
**Status**: PASS-WITH-EVIDENCE (FINAL-A A6 anchor check + A6 byte-exact + A7 drop complete)

## Provenance

- **Source TSV**: `D:/stem/testdata/stem.testdata.tsv`
  - `source_sha256 = 9e6dba16d1dcfcb4ea39226066e7c3bc53c0175888122134e8357285cef54514`
  - 1999 ENSG-Mus-musculus genes; 10 columns (gene_id, gene_name, plus 8 Brain time-points).
- **Analysis main.txt**: derived from source TSV by selecting the 7 Brain columns in biological developmental order and dropping `gene_id` (kept `gene_name` as the ID column, `spot_included=false`).
  - `analysis_input_sha256 = ef8e6ae3915c50bcef518d737b915e9e36d83bb2bb02c59cf643b27a105a45ac`
  - Header: `gene_name \t E10.5_Brain \t E12.5_Brain \t E14.5_Brain \t E16.5_Brain \t P0_Brain \t P21_Brain \t 8W_Brain`
  - 1999 data rows, LF line endings, UTF-8 (no BOM).

## Anchor check (P0 if violated)

| metric | expected | actual |
|---|---|---|
| input rows | 1999 | **1999** |
| retained genes | 1635 | **1635** |
| model profiles | 50 | **50** |
| significant profiles | 7 | **7** |
| significant profile ids | {10,16,17,39,41,44,49} | **{10,16,17,39,41,44,49}** |

## Byte-exact comparison (C2)

| comparison | genetable | profiletable |
|---|---|---|
| Python API == Python CLI | **byte-exact** | **byte-exact** |
| Python API == Java STEM v1.3.14 | **byte-exact** | **byte-exact** |

Python API: `D:/stem/pySTEMtc/verification/r1_canonical/main_genetable.txt` (and `_profiletable.txt`)
Python CLI: `D:/stem/pySTEMtc/verification/r1_canonical_cli/R1_genetable.txt` (and `_profiletable.txt`)
Java reference: `D:/stem/pySTEMtc/verification/r1_canonical_java_genetable.txt` (and `_profiletable.txt`)
Java invocation: `java -cp D:/stem/stem.jar edu.cmu.cs.sb.stem.ST -b <cfg_dir> <out_dir>`

## Algorithm config (frozen for R1)

| key | value |
|---|---|
| Normalize_Data | Log normalize data |
| Spot_IDs_included_in_the_data_file | false |
| Maximum_Number_of_Missing_Values | 1 |
| Minimum_Absolute_Log_Ratio_Expression | 0.5 |
| Change_should_be_based_on | Maximum-Minimum |
| Maximum_Number_of_Model_Profiles | 50 |
| Maximum_Unit_Change_in_Model_Profiles_between_Time_Points | 2 |
| Maximum_Correlation | 1.0 |
| Number_of_Permutations_per_Gene | 50 |
| Permutation_Test_Should_Permute_Time_Point_0 | true |
| Significance_Level | 0.05 |
| Correction_Method | Bonferroni |
| Clustering_Minimum_Correlation | 0.7 |
| Clustering_Minimum_Correlation_Percentile | 0.0 |

## CLI smoke (A4 exit-code contract)

- `pystemtc run` on the canonical config: **exit 0** (see `cli_run.log`).
- `pystemtc batch` over a directory containing one good config + one bad config:
  - bad config fails (`Data_File not found`), **batch continues**
  - good config completes (writes both tables)
  - batch process **exit 1** (at least one config failed) -- see `cli_batch.log`

## What's in this directory

| file | size | provenance |
|---|---|---|
| `source_manifest.yaml` | 1817 | copy of `verification/round75_R1v2_manifest.yaml` |
| `main.txt` | 164248 | canonical analysis input (hash matches `ef8e6ae3915c50...`) |
| `R1_brain_trajectory_genetable.txt` | 90079 | pystemtc Python API output (GBK + CRLF) |
| `R1_brain_trajectory_profiletable.txt` | 3364 | pystemtc Python API output (GBK + CRLF) |
| `java_R1_brain_trajectory_genetable.txt` | 90079 | Java STEM v1.3.14 output (GBK + CRLF) |
| `java_R1_brain_trajectory_profiletable.txt` | 3364 | Java STEM v1.3.14 output (GBK + CRLF) |
| `testdata_result_summary.md` | (this file) | A6 / A7 evidence summary |
| `pytest_full.log` | 27649 | full pytest run, **281 passed in 468.37s** (FINAL-A A8 real number) |
| `cli_run.log` | 416 | captured stdout + stderr + exit code from `pystemtc run` (exit 0) |
| `cli_batch.log` | 748 | captured stdout + stderr + exit code from `pystemtc batch` (exit 1, 1/2 configs failed by design) |
| `provenance.txt` | 1470 | toolchain snapshot (Python, NumPy, Java, stem.jar SHA256, platform) |

## Per-suite pytest counts (FINAL-A A8, all green)

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

9 warnings in the full run are all the M5 warning firing on the `c04_add0` and `headers_custom` golden cases (where the M5 combination is intentional and exercised as a byte-exact oracle).
