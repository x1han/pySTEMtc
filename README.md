# pySTEMTC

A headless Python port of **STEM v1.3.14** (Short Time-series Expression Miner;
Java reference at <https://ernstlab.github.io/STEM/>).  pySTEMTC implements the
M1 normalization / filtering chain and the M2 STEM clustering algorithm with
**byte-exact equivalence** to the Java original on the testdata R1 Brain
trajectory.

> **Status**: V1 frozen.  Algorithm development is **FROZEN** as of FINAL-B.
> Ready for real time-course datasets: **YES**.

## TL;DR

- pySTEMTC is a normal Python package, not just a CLI.  `import pystemtc` works
  in any Python process, including Jupyter notebooks.
- The `pystemtc run` / `pystemtc batch` commands you see in the wheel are thin
  wrappers over `pystemtc.engine.STEM.fit`.  Pick whichever surface fits your
  workflow; the algorithm surface is identical.
- For byte-exact comparison against the Java golden, pass
  `encoding="gbk", newline="\r\n"` when writing tables (Windows JRE 1.8.0_451
  defaults).

## Install

```bash
pip install pystemtc-1.0.0-py3-none-any.whl
```

The wheel installs a single console script `pystemtc` plus the `pystemtc`
Python package.  Runtime deps pulled in: `numpy` and `pandas`.

## Two ways to use it

| if you want to ... | use | see |
|---|---|---|
| drive the run from a shell script, a Makefile, or a CI step | `pystemtc run` / `pystemtc batch` (CLI) | [CLI](#cli) |
| call it from a Python script, Jupyter notebook, or test suite | `import pystemtc` (Python API) | [Python API](#python-api) |

Both call the same `pystemtc.engine.STEM.fit` underneath; the CLI just
parses `defaults.txt` and resolves relative paths for you.

## What V1 covers

- The Java M1 chain (`read -> logratio2 -> averageAndFilterDuplicates ->
  repeat merge -> filterdistprofiles -> filterMissing ->
  filtergenesthreshold2`).
- The Java M2 STEM clustering method (`STEM Clustering Method`).
- Java-compatible genetable and profiletable writer (M4).

## What V1 does NOT cover (frozen V1 scope)

- K-means clustering method (`NotImplementedError`).
- Two-condition comparison / GO / KEGG enrichment.
- GUI / plot / interactive display.
- R2 / R3 (future work).

## Python API

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

Pick the recipe that matches your data:

### Recipe 1 — from a `defaults.txt` (canonical real-data path)

> **Prefer the CLI for this path.** If you already have a Java
> `defaults.txt`, the CLI (`pystemtc run`) is the canonical and least
> error-prone entry point — it parses the config, resolves `Data_File` /
> `Repeat_Data_Files` relative to the config's directory (mirrors Java STEM),
> and maps every V1 algorithm field into the engine for you.
>
> For notebook / API use, you must reproduce both the configuration
> mapping **and** the config-relative path resolution yourself. The recipe
> below does exactly that; copy it verbatim unless you specifically want to
> override a field. Any V1 algorithm field you omit here falls back to
> `STEM()`'s Python default, which will not match your `defaults.txt`.

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

> **Note** — `replicates=` is **required** when the defaults file has a
> non-empty `Repeat_Data_Files` line.  The engine does not re-read the config
> for repeats on the fit() call, so the API takes them explicitly.  Pass
> `None` (or omit) when the config has no repeats.
> See `verification/derive_r1_brain7.py` for the canonical real-data run.

### Recipe 2 — from an in-memory `pandas.DataFrame` (notebook-friendly headline)

Skip the file IO.  Hand the engine a wide DataFrame with a required
`gene` column and an optional `spot` column. Every other column is treated
as a time point in the DataFrame's existing column order.

**Time-point order matters.** Every column other than `gene` and optional
`spot` is interpreted as a time point in the DataFrame's existing column
order, so arrange those columns in the intended biological sequence before
calling `fit()`.

For `normalize="log"` and `normalize="normalize"`, the first input
time-point column is v0 / time point 0 and is used as the normalization
reference. For `normalize="none_add0"`, Java STEM instead prepends a
synthetic zero: `(v0, v1, ...)` -> `(0, v0, v1, ...)`. The original
DataFrame columns must still remain in their intended sequential order.

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
result = engine.fit(df)              # no defaults.txt on disk

# inspect in memory (see "Inspecting the result" below):
print(result.metadata["num_genes"], "genes retained")
print(result.gene_assignments[0].profile_ids)
```

When you do want to write the table from a DataFrame, you must pass an
explicit `prefix=` — `write_java_tables` cannot derive one from a DataFrame
because there is no path stem to read:

```python
result.write_java_tables("out/", prefix="my_run", encoding="gbk", newline="\r\n")
```

### Recipe 3 — from a pre-built `STEMDataset` (advanced / custom M1)

If you have already done M1 yourself (custom normalization, custom
imputation, custom merging), build a `STEMDataset` and pass it directly.
This skips M1 entirely; `result.timing["input_read"]` and
`result.timing["normalize_filter"]` then report `0.0`.  See
`tests/test_units_m2.py` lines 179-232 for a complete worked example and
`pystemtc.dataset.build_stem_dataset` for the factory.

## Inspecting the result without writing files

`engine.fit(...)` returns a `STEMResult` (a `@dataclass`).  All fields are
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

## Writing the Java-shaped tables

```python
result.write_java_tables(
    out_dir="out/",
    prefix="my_run",                    # required when input was a DataFrame
    encoding="gbk",                     # None = platform default
    newline="\r\n",                     # None = platform default
)
```

Returns a `list[str]` of two absolute paths in the order
`[genetable, profiletable]`.  When `prefix=None` and the input was a path,
the prefix defaults to the stem of `result.input["data_file"]`.  When
`prefix=None` and the input was a DataFrame (no stem to derive), raises
`ValueError`.

For C2 byte-exact comparison against the Java golden (JRE 1.8.0_451 / GBK /
CRLF on Windows), pass `encoding="gbk", newline="\r\n"` explicitly.  The
default (`None`) is the platform default — readable on the host, not
guaranteed byte-exact vs Java.

## M5 warning (frozen text)

When `normalize='none_add0'` is combined with `permute_t0=True`, the engine
emits **one** `UserWarning` per analysis with this exact text:

> normalize='none_add0' with permute_t0=True permutes the synthetic zero
> baseline together with observed time points, matching legacy STEM v1.3.14
> behavior. Interpret permutation-based significance with caution.

The text lives in `pystemtc.engine.M5_WARNING` (single source of truth) and
the test suite asserts full equality against it.

Silence the warning at the application boundary:

```python
import warnings
warnings.filterwarnings(
    "ignore",
    message=r"normalize='none_add0'.*Interpret permutation-based significance with caution",
    category=UserWarning,
)
```

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

**Byte-exact vs Java on Windows**: For C2 byte-exact output, the writer
must receive GBK + a literal CRLF line terminator. Shell quoting for CRLF
is **shell-specific** — `$'\r\n'` is Bash / Git Bash ANSI-C quoting and is
NOT portable to PowerShell / CMD.

Bash / Git Bash:

```bash
pystemtc run --config defaults.txt --output out/ --encoding gbk --newline $'\r\n'
```

For Python / API use, the unambiguous form is:

```python
result.write_java_tables("out/", prefix=..., encoding="gbk", newline="\r\n")
```

The default (`None`) is the platform default — readable on the host, not
guaranteed byte-exact vs Java (LF on Linux/macOS, CRLF on Windows).

**Relative paths** in `Data_File` / `Repeat_Data_Files` are resolved against
the config file's own directory, not the current working directory (mirrors
Java STEM).

`pystemtc run --help` and `pystemtc batch --help`: Both subcommands
expose `--output`, `--encoding`, and `--newline`; `run` takes `--config`
(an individual `defaults.txt`), while `batch` takes `--config-dir`
(a directory of `defaults.txt` files).

## Tests

```bash
pip install -e ".[dev]"
pytest -q                                # 285 tests, ~8 minutes (Java reference comparison)
```

The CLI sub-suite (`tests/test_cli.py`, 14 tests) covers both subcommands,
exit codes, batch-continues-on-failure, relative-path resolution, two
byte-exact CLI vs Java oracle cases (c01 different-period and c07
same-period), and a three-way c01/c07/c08 distinct-output regression guard.

## License

GPL-3.0 (this port inherits the Java STEM v1.3.14 license).