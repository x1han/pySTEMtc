# pySTEMTC V1

A headless Python port of **STEM v1.3.14** (Short Time-series Expression Miner;
Java reference at <https://ernstlab.github.io/STEM/>).  pySTEMTC implements the
M1 normalization / filtering chain and the M2 STEM clustering algorithm with
**byte-exact equivalence** to the Java original on the testdata R1 Brain
trajectory.

> **Status**: V1 frozen.  Algorithm development is **FROZEN** as of FINAL-B.
> Ready for real time-course datasets: **YES**.

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
- R2/R3 (future work).

## Install

```bash
pip install pystemtc-1.0.0-py3-none-any.whl
```

The wheel installs a single console script `pystemtc`.

## Python API

```python
from pystemtc import STEM, STEMConfig

cfg = STEMConfig.from_defaults_file("defaults.txt")
engine = STEM(
    normalize=cfg.normalize,
    max_unit_change=cfg.max_unit_change,
    max_model_profiles=cfg.max_model_profiles,
    # ... pass every config field you want to override
    repeat_mode=cfg.repeat_mode,
)
result = engine.fit(
    cfg.data_file,
    replicates=cfg.repeat_files or None,
)
result.write_java_tables("out/", prefix="my_run")
```

**Important**: when reading a `defaults.txt` via `STEMConfig.from_defaults_file`,
**always pass `replicates=cfg.repeat_files or None`** to `engine.fit()`.  The
config object parses `Repeat_Data_Files` correctly; the engine does not
read it back from the config -- the API takes the repeat list as an
explicit argument so the same engine works on in-memory `DataFrame`s.
The CLI does this wiring automatically.  `cfg.repeat_mode`
(`"different_periods"` | `"same_period"`) controls how the repeat set is
merged into the main set and is passed via `STEM(repeat_mode=...)`.

See `verification/derive_r1_brain7.py` for the canonical run pattern.

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
| 2 | CLI usage error |

**Byte-exact vs Java on Windows**: pass `--encoding gbk --newline $'\r\n'` to
match JRE 1.8.0_451's GBK + CRLF defaults.  Defaults are platform-default for
readability on the host (LF on Linux/macOS, CRLF on Windows).

**Relative paths** in `Data_File` / `Repeat_Data_Files` are resolved against
the config file's own directory, not the current working directory (mirrors
Java STEM).

## M5 warning (frozen text)

When `normalize='none_add0'` and `permute_t0=True` are both set, the engine
emits **one** `UserWarning` per analysis with this frozen text:

> M5: normalize='none_add0' with permute_t0=True permutes the synthetic zero
> baseline together with observed time points, matching legacy STEM v1.3.14
> behavior. Interpret permutation-based significance with caution.

## Tests

```bash
pip install -e .[dev]
pytest            # 281 tests, ~8 minutes (Java reference comparison)
```

## License

GPL-3.0 (this port inherits the Java STEM v1.3.14 license).
