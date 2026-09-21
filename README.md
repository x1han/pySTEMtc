# pySTEMtc

**STEM time-course clustering for Python.**

pySTEMtc is a native Python implementation of the STEM time-course
analysis workflow, designed for reproducible programmatic use in scripts,
notebooks, and automated pipelines. It provides a scriptable Python API
and a command-line interface for short time-series clustering without
requiring the original Java GUI.

The project implements the core STEM workflow end to end:

- time-course expression input and replicate handling
- normalization and filtering
- model profile generation
- gene-to-profile assignment
- permutation-based expected counts
- statistical significance and multiple-testing correction
- STEM profile clustering
- Java-compatible result tables
- CLI and Python API workflows

pySTEMtc is designed for researchers who want to integrate STEM-style
analysis directly into Python, notebooks, automated pipelines, and
reproducible computational workflows.

## Why pySTEMtc?

The original STEM software established a widely used approach for
clustering short biological time series. pySTEMtc brings that workflow
into a modern Python environment while preserving scientifically
important behavior.

Key features include:

- **Python-native** — no JVM bridge or Java subprocess is required for analysis
- **Scriptable** — use the Python API from notebooks, scripts, or larger pipelines
- **Command-line ready** — run individual analyses or batches from STEM-style configuration files
- **Deterministic** — compatibility-sensitive random procedures reproduce Java STEM execution semantics
- **Replicate-aware** — supports both same-period and different-period replicate workflows
- **Validated** — core results are continuously checked against Java STEM v1.3.14 reference outputs
- **Interoperable** — Java-compatible gene and profile tables can be reproduced when required

## What pySTEMtc adds

These are engineering capabilities of pySTEMtc, not features of the
original Java GUI workflow:

- Native Python implementation
- Python object API
- DataFrame integration
- Headless execution
- Batch CLI
- Reproducible deterministic execution
- Automated Java-oracle compatibility tests
- Byte-exact table reproduction
- Explicit missing-value representation
- Modern packaging
- Cross-platform test infrastructure
- Real-data acceptance suite

The Python implementation, programmatic API, command-line interface,
compatibility layer, deterministic execution framework, regression suite,
and release infrastructure are developed as part of the pySTEMtc project.

## Installation

```bash
pip install pystemtc-1.0.0-py3-none-any.whl
```

The wheel installs a single console script `pystemtc` plus the
`pystemtc` Python package. Runtime deps pulled in: `numpy` and `pandas`.

## Quick start

### Command-line

```bash
# Run a single STEM-style config:
pystemtc run --config defaults.txt --output out/

# Run every config in a directory (continues on per-config failure):
pystemtc batch --config-dir configs/ --output out/
```

### Python API

```python
import pandas as pd
from pystemtc import STEM

df = pd.DataFrame({
    "gene":  ["Gnai3", "Cdc45", "Thbd"],
    "E10.5": [183.4, 62.4, 14.1],
    "E12.5": [167.7, 35.9, 11.7],
    "E14.5": [ 96.5,  6.6,  9.3],
    "E16.5": [105.3,  9.3,  7.8],
    "P0":    [ 80.7,  2.4,  6.2],
    "P21":   [ 22.3,  1.0,  4.9],
    "8W":    [ 33.3,  2.4,  5.1],
})

engine = STEM(normalize="log", n_permutations=50)
result = engine.fit(df)
print(result.metadata["num_genes"], "genes retained")
```

### From a `defaults.txt` (notebook / API use)

> **Prefer the CLI for this path.** If you already have a Java
> `defaults.txt`, the CLI (`pystemtc run`) is the canonical and least
> error-prone entry point — it parses the config, resolves `Data_File` /
> `Repeat_Data_Files` relative to the config's directory, and maps every
> V1 algorithm field into the engine for you.
>
> For notebook / API use, you must reproduce both the configuration
> mapping **and** the config-relative path resolution yourself. The
> recipe below does exactly that; copy it verbatim unless you specifically
> want to override a field. Any V1 algorithm field you omit here falls
> back to `STEM()`'s Python default, which will not match your
> `defaults.txt`.

```python
from pathlib import Path
from pystemtc import STEM, STEMConfig

config_path = Path("defaults.txt").resolve()
cfg = STEMConfig.from_defaults_file(config_path)

def resolve_from_config(path):
    p = Path(path)
    return p if p.is_absolute() else config_path.parent / p

engine = STEM(
    normalize=cfg.normalize,
    max_missing=cfg.max_missing,
    min_abs_expr=cfg.min_abs_expr,
    change_rule="max_minus_min" if cfg.maxmin else "diff_from_zero",
    repeat_min_correlation=cfg.repeat_min_correlation,
    spot_included=cfg.spot_included,
    repeat_mode=cfg.repeat_mode,
    max_model_profiles=cfg.max_model_profiles,
    max_unit_change=cfg.max_unit_change,
    max_correlation=cfg.max_correlation,
    candidate_cap=cfg.candidate_cap,
    n_permutations=cfg.n_permutations,
    permute_t0=cfg.permute_t0,
    alpha=cfg.alpha,
    correction=cfg.correction,
    cluster_min_correlation=cfg.cluster_min_correlation,
    cluster_corr_percentile=cfg.cluster_corr_percentile,
    clustering_method=cfg.clustering_method,
)

data_file = resolve_from_config(cfg.data_file)
repeat_files = [resolve_from_config(p) for p in cfg.repeat_files]

result = engine.fit(
    data_file,
    replicates=repeat_files or None,
)
result.write_java_tables("out/", prefix="my_run")
```

Public re-exports from `pystemtc.__init__` (main public re-exports; the
full list lives in `pystemtc.__all__`):

```python
from pystemtc import (
    STEM,                # the engine
    STEMConfig,          # defaults.txt parser / dataclass
    STEMDataset,         # pre-built dataset (advanced use)
    SpotSet,             # raw M1 input shape
    STEMResult,          # what fit() returns
    ProfileRecord,       # one row of result.profiles
    GeneAssignment,      # one row of result.gene_assignments
    STEMTCValueError,    # input / config error
    __version__,         # e.g. "1.0.0"
)
```

## Input format

Hand the engine a wide DataFrame with a required `gene` column and an
optional `spot` column. Every other column is treated as a time point in
the DataFrame's existing column order.

**Time-point order matters.** Every column other than `gene` and optional
`spot` is interpreted as a time point in the DataFrame's existing column
order, so arrange those columns in the intended biological sequence before
calling `fit()`.

For `normalize="log"` and `normalize="normalize"`, the first input
time-point column is v0 / time point 0 and is used as the normalization
reference. For `normalize="none_add0"`, Java STEM instead prepends a
synthetic zero: `(v0, v1, ...)` -> `(0, v0, v1, ...)`. The original
DataFrame columns must still remain in their intended sequential order.

The `gene` and optional `spot` columns may appear anywhere; they are
identified by name. Pass `spot` only when your Java config has
`Spot_IDs_included_in_the_data_file=true`.

## Replicates

pySTEMtc supports both STEM replicate modes:

- **Different time periods** — repeats are merged after normalization.
- **The same time period** — repeats are merged before normalization
  (different code path; uses the Java reference at
  `DataSetCore.java:787-792`).

Configure with `repeat_mode=` on `STEM()` or
`Repeat_Mode_includes_the_data_file` in `defaults.txt`. On the CLI, the
mode is taken from the config; for the Python API, pass
`replicates=` to `engine.fit()`:

```python
result = engine.fit(
    data_file,
    replicates=repeat_files or None,   # None when the config has no repeats
)
```

`replicates=` is **required** when the defaults file has a non-empty
`Repeat_Data_Files` line. The engine does not re-read the config for
repeats on the `fit()` call, so the API takes them explicitly.

## Outputs

`engine.fit(...)` returns a `STEMResult` (a `@dataclass`). All fields are
public; there is no `to_` setter or private state.

```python
result.gene_assignments   # list[GeneAssignment]    -- one per retained gene
result.profiles           # list[ProfileRecord]     -- one per model profile
result.filtered_genes     # list[(gene, probe, reason)]  -- dropped genes
result.clusters           # list[list[int]]         -- cluster_id -> member profile ids
result.config             # dict                   -- the resolved config
result.metadata           # dict                   -- num_genes, num_profiles, ...
result.input              # dict                   -- input form / paths / time points
result.timing             # dict                   -- per-stage wall seconds
```

`GeneAssignment` (per gene):

| field | type | meaning |
|---|---|---|
| `gene` | `str` | gene symbol |
| `probe` | `str` | SPOT/probe id (merged-probe string when duplicates merged) |
| `profile_ids` | `list[int]` | assigned profile ids; several when tied, ascending model-index order |
| `values` | `list[float]` | normalized (post-merge) stored doubles; may include NaN / ±Inf |
| `present` | `list[bool]` | Java pma != 0 per column |

`ProfileRecord` (per model profile):

| field | type | meaning |
|---|---|---|
| `id` | `int` | profile id |
| `model` | `list[float]` | the model profile coordinates (one per time point) |
| `cluster` | `int` | `-1` means non-significant or unclustered |
| `n_assigned` | `float` | fractional weights from 1/k ties are expected |
| `n_expected` | `float` | expected count under null |
| `p_value` | `float` | raw p-value |
| `significant` | `bool` | post-correction significance flag |

For JSON-safe serialization (NaN/±Inf encoded as `None` plus a parallel
`value_states` list):

```python
import json
payload = result.to_dict()                      # schema-v2 dict
json.dumps(payload, allow_nan=False)            # succeeds; no NaN literals
```

Writing the Java-shaped genetable and profiletable:

```python
result.write_java_tables(
    out_dir="out/",
    prefix="my_run",                    # required when input was a DataFrame
    encoding="gbk",                     # None = platform default
    newline="\r\n",                     # None = platform default
)
```

Returns a `list[str]` of two absolute paths in the order
`[genetable, profiletable]`. When `prefix=None` and the input was a path,
the prefix defaults to the stem of `result.input["data_file"]`. When
`prefix=None` and the input was a DataFrame (no stem to derive), raises
`ValueError`.

## Statistical workflow

- Permutation-based expected counts via the same RNG, baseline, and
  re-referencing semantics as Java STEM v1.3.14 (see
  `src/pystemtc/permutation.py`).
- Multiple-testing correction: `bonferroni`, `fdr`, or `none`
  (`Correction_Method` in `defaults.txt`).
- Significance flag (`Significant` column in the profiletable) reflects
  the post-correction test.

The on-the-fly permutation path is used automatically for large
candidate universes; the in-memory path is used otherwise.

## Compatibility with STEM v1.3.14

pySTEMtc uses Java STEM v1.3.14 as the reference implementation for
compatibility validation.

Compatibility testing covers model profiles, assignments, expected
counts, statistical significance, profile clustering, replicate
workflows, formatted output tables, and deterministic random
procedures.

The compatibility suite includes decoded-content comparisons and
byte-exact reference tests against Java-generated outputs. Real STEM
test data are also used for end-to-end validation.

Compatibility is a validation target — pySTEMtc itself is a native
Python implementation and does not require Java for normal analysis.

### Byte-exact output (C2)

For byte-exact comparison against the Java golden (JRE 1.8.0_451 / GBK
/ CRLF on Windows):

```python
result.write_java_tables("out/", prefix=..., encoding="gbk", newline="\r\n")
```

From the CLI, the unambiguous form is shell-specific:

```bash
# Bash / Git Bash
pystemtc run --config defaults.txt --output out/ --encoding gbk --newline $'\r\n'
```

`$'...'` is Bash / Git Bash ANSI-C quoting and is not portable to
PowerShell / CMD. For Python / API use, the unambiguous form is
`encoding="gbk", newline="\r\n"`.

### M5 warning (frozen text)

When `normalize='none_add0'` is combined with `permute_t0=True`, the
engine emits **one** `UserWarning` per analysis with this exact text:

> normalize='none_add0' with permute_t0=True permutes the synthetic zero
> baseline together with observed time points, matching legacy STEM v1.3.14
> behavior. Interpret permutation-based significance with caution.

The text lives in `pystemtc.engine.M5_WARNING` (single source of truth)
and the test suite asserts full equality against it.

Silence the warning at the application boundary:

```python
import warnings
warnings.filterwarnings(
    "ignore",
    message=r"normalize='none_add0'.*Interpret permutation-based significance with caution",
    category=UserWarning,
)
```

## Validation

- 285 unit + integration + golden tests, runnable locally via
  `pytest -q`. Full run is ~8 minutes due to Java-oracle byte-exact
  comparisons.
- The CLI sub-suite (`tests/test_cli.py`, 14 tests) covers both
  subcommands, exit codes, batch-continues-on-failure, relative-path
  resolution, two byte-exact CLI vs Java oracle cases (c01
  different-period and c07 same-period), and a three-way c01/c07/c08
  distinct-output regression guard.
- Real-data end-to-end run against `D:/stem/testdata/stem.testdata.tsv`
  (Brain trajectory, 1999 genes × 7 time points) with byte-exact
  match against the Java reference. See
  `verification/derive_r1_brain7.py` and
  `final_acceptance/R1_brain_trajectory/`.
- Cross-platform CI matrix on GitHub Actions: Windows + Linux × Python
  3.11 / 3.12 / 3.14, `pip install -e ".[dev]"`, `pytest -q`.

## Scope / limitations

Out of V1 scope (will not be added):

- K-means clustering method (`NotImplementedError`).
- Two-condition comparison / GO / KEGG enrichment.
- GUI / interactive display.
- R2 / R3 (future work).

## CLI

```bash
# Run a single config:
pystemtc run --config defaults.txt --output out/

# Run every config in a directory (continues on per-config failure):
pystemtc batch --config-dir configs/ --output out/
```

**Exit codes**

| code | meaning |
|---|---|
| 0 | success |
| 1 | analysis / config / I/O failure (per-config in batch mode) |
| 2 | CLI usage error (bad args, missing `--config` / `--output`, config not found, ...) |

**Relative paths** in `Data_File` / `Repeat_Data_Files` are resolved
against the config file's own directory, not the current working
directory (mirrors Java STEM).

`pystemtc run --help` and `pystemtc batch --help`: Both subcommands
expose `--output`, `--encoding`, and `--newline`; `run` takes `--config`
(an individual `defaults.txt`), while `batch` takes `--config-dir`
(a directory of `defaults.txt` files).

## Tests

```bash
pip install -e ".[dev]"
pytest -q                                # 285 tests, ~8 minutes (Java reference comparison)
```

## Citation

When citing pySTEMtc, please cite it as a native Python implementation
of STEM time-course clustering validated against Java STEM v1.3.14.

## Scientific origin & acknowledgements

STEM was originally developed by Jason Ernst and Ziv Bar-Joseph for the
analysis of short biological time series. pySTEMtc implements the STEM
time-course methodology in Python and uses Java STEM v1.3.14 as its
primary compatibility reference.

The Python implementation, programmatic API, command-line interface,
compatibility layer, deterministic execution framework, regression
suite, and release infrastructure are developed as part of the
pySTEMtc project.

## License

GPL-3.0 (this port inherits the Java STEM v1.3.14 license).