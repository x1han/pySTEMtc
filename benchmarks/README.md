# benchmarks/ — pySTEMTC re-runnable performance harness

Re-runnable benchmark harness for the pySTEMTC core pipeline (round 6,
HANDOFF D15).  `python benchmarks/benchmark_core.py` runs the core group
B1-B6 (deterministic synthetic input, 50 permutations, 50 model profiles,
normalize mode) in isolated subprocesses and writes a long-table CSV plus a
summary Markdown into `results/<UTC timestamp>/`.

## Relationship to `tools/bench.py` (do not confuse the two)

- `tools/bench.py` = the **M3 one-shot evidence** run (round-5 ruling N3,
  "measure only, do not optimize").  It is frozen: never edit it, never
  import from it.
- `benchmarks/benchmark_core.py` = the **re-runnable harness**: warm-up +
  formal repetitions, median aggregation (min/max kept, never averaged),
  per-stage timing from `result.timing`, process-isolated peak RSS, and
  deterministic outputs under version control (`results/.gitkeep`).

## Directory discipline (HANDOFF D15)

- `tests/golden/` proves the engine computes the **same** results as Java
  (acceptance); `benchmarks/` records how **fast** it computes them
  (records).  The two are separate concerns with separate directories.
- This directory never imports `tests/` (nor reads `tests/golden/`) and
  never imports `tools/` — the synthetic-data generator below re-implements
  the shared conventions (N(0,1), 3 decimals, dup_every=10 duplicate
  structure, no missing cells, SPOT column) independently.
- **Any optimization: full golden run (all pass) -> optimize -> full golden
  run again.**  Golden proves "computes the same"; benchmarks prove
  "computes this fast"; a benchmark number never replaces the golden
  criterion.  Scratch data files land in `_scratch/` (gitignored).

## Groups and flags

| group | ids | definition |
|---|---|---|
| core (default) | B1-B9 | round-6 named grid plus round-7 transition-diagnostic point: B1=1000x5T, B2=5000x5T, B3=10000x5T, B4=30000x5T, B5=10000x8T, **B9=10000x9T** (T=9 falls in the on_the_fly + enumerate intersection, the boundary where B5→B6 path-switching is observable but the steps co-vary too much for single-factor decomposition), B6=10000x10T; no repeat files |
| `--sweep` | S10/S50/S100/S500/S1000 | 10000x8T with `n_permutations` in {10, 50, 100, 500, 1000} (50 model profiles) |
| `--reps` | B7, B8 | 10000x5T and 10000x10T, each with 2 repeat files (`different_periods`) |

Flags: `--bench B1,B4` (subset), `--all`, `--warmup N` (default 1),
`--formal N` (default 3), `--seed` (default 20260919), `--outdir`
(default `benchmarks/results/<UTCts>`).  `--worker`/`--bench-id`/`--input`
are hidden internal modes (one bench, one run, one JSON line on stdout).

Peak RSS is measured inside the isolated worker process: Windows via Psapi
`GetProcessMemoryInfo` -> `PeakWorkingSetSize` (ctypes; implementation
copied from `tools/bench.py`, attribution noted inline), Linux via
`resource.getrusage(...).ru_maxrss * 1024`, macOS via `ru_maxrss` as-is.

## Records

`results/` holds the committed-but-empty marker only; each run creates its
own `results/<UTCts>/<UTCts>_core.csv` + `_core.md` pair.  Keep the newest
pair when committing measurement records; do not hand-edit them.
