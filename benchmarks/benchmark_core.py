"""Re-runnable performance harness for the pySTEMTC core (round-6, D15).

Directory discipline (HANDOFF D15): ``tests/golden/`` proves the engine
computes the SAME results as Java (acceptance); ``benchmarks/`` records how
FAST it computes them (records).  The two never import each other and this
script never reads ``tests/`` — including ``tests/golden`` — nor ``tools/``
(the M3 one-shot evidence tool ``tools/bench.py`` stays frozen; the
synthesizer below re-implements its conventions independently).

Any optimization must follow: full golden run (all pass) -> optimize -> full
golden run again.  Benchmark numbers only inform the decision; they never
replace the golden criterion.

Groups (default = core B1-B6, the round-6 named grid):
- B1..B6  core scaling grid, 0 repeat files:
          B1=1k x 5T, B2=5k x 5T, B3=10k x 5T, B4=30k x 5T,
          B5=10k x 8T, B6=10k x 10T
- --sweep S10/S50/S100/S500/S1000: 10000 spots x 8T with
          n_permutations in {10, 50, 100, 500, 1000} (not part of smoke)
- --reps  B7 = 10000x5T and B8 = 10000x10T, each with 2 repeat files
          (different_periods), exercising the repeat-merge path

Each (benchmark, run) executes in a fresh subprocess (``--worker`` hidden
mode) so peak RSS is process-monotonic per run: warm-up runs are discarded,
formal runs are aggregated by MEDIAN (min/max kept, never averaged).

Usage:
  python benchmarks/benchmark_core.py                     # core B1-B6
  python benchmarks/benchmark_core.py --bench B1,B4      # subset
  python benchmarks/benchmark_core.py --sweep            # permutation-count sweep
  python benchmarks/benchmark_core.py --reps             # repeat-file group
  python benchmarks/benchmark_core.py --all
  python benchmarks/benchmark_core.py --bench B1 --formal 1   # smoke

Outputs: <outdir>/<ts>_core.csv (long table, one row per run) and
<outdir>/<ts>_core.md (summary + environment header), with
<outdir> defaulting to benchmarks/results/<UTC timestamp>.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform as _platform
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
if str(_PROJECT / "src") not in sys.path:
    sys.path.insert(0, str(_PROJECT / "src"))

SCRATCH = _HERE / "_scratch"
RESULTS = _HERE / "results"

SEED_DEFAULT = 20260919


@dataclass(frozen=True)
class BenchSpec:
    bench_id: str
    spots: int
    time_points: int
    repeat_files: int = 0
    max_model_profiles: int = 50
    n_permutations: int = 50
    group: str = "core"  # core | sweep | repeats


CORE: list[BenchSpec] = [
    BenchSpec("B1", 1_000, 5),
    BenchSpec("B2", 5_000, 5),
    BenchSpec("B3", 10_000, 5),
    BenchSpec("B4", 30_000, 5),
    BenchSpec("B5", 10_000, 8),
    BenchSpec("B6", 10_000, 10),
]
SWEEP: list[BenchSpec] = [
    BenchSpec(f"S{n}", 10_000, 8, n_permutations=n, group="sweep")
    for n in (10, 50, 100, 500, 1000)
]
REPEATS: list[BenchSpec] = [
    BenchSpec("B7", 10_000, 5, repeat_files=2, group="repeats"),
    BenchSpec("B8", 10_000, 10, repeat_files=2, group="repeats"),
]
ALL_SPECS: dict[str, BenchSpec] = {
    spec.bench_id: spec for spec in CORE + SWEEP + REPEATS
}

STAGE_KEYS = (
    "input_read",
    "normalize_filter",
    "profile_generation",
    "assignment",
    "permutation",
    "significance",
    "clustering",
)


# --------------------------------------------------------------------------
# synthetic input (same conventions as tools/bench.py, independent code)
# --------------------------------------------------------------------------


def _write_synth(path: Path, n_spots: int, n_cols: int, seed: int) -> None:
    """Deterministic STEM tsv: values ~ N(0,1), 3 decimals, dup_every=10
    duplicate structure, no missing cells, SPOT column, t0..t{T-1} header.
    normalize mode; the same conventions as the M3 evidence tool, but
    implemented here so benchmarks/ never imports tools/."""
    import numpy as np

    rng = np.random.default_rng(seed)
    values = rng.normal(0.0, 1.0, size=(n_spots, n_cols))
    genes: list[str] = []
    for i in range(n_spots):
        if i % 10 == 1 and genes:
            genes.append(genes[-1])  # duplicate the previous gene
        else:
            genes.append(f"GENE_{i:06d}")
    with open(path, "w", newline="\n") as fh:
        fh.write("SPOT\tGene Symbol\t" + "\t".join(f"t{j}" for j in range(n_cols)) + "\n")
        for i in range(n_spots):
            cells = [str(i + 1), genes[i]]
            cells += [f"{values[i, j]:.3f}" for j in range(n_cols)]
            fh.write("\t".join(cells) + "\n")


def _ensure_inputs(spec: BenchSpec, seed: int) -> list[Path]:
    """Write (once per seed) the main + repeat data files for a bench.  The
    seed is part of the filename so a run with a different --seed can never
    silently reuse data generated under an older seed while labelling its
    record with the new one."""
    SCRATCH.mkdir(parents=True, exist_ok=True)
    stem = SCRATCH / f"{spec.bench_id}_{spec.spots}x{spec.time_points}_seed{seed}"
    paths = [stem.with_suffix(".txt")]
    if not paths[0].exists():
        _write_synth(paths[0], spec.spots, spec.time_points, seed)
    for k in range(spec.repeat_files):
        rep = SCRATCH / f"{spec.bench_id}_{spec.spots}x{spec.time_points}_seed{seed}_rep{k + 1}.txt"
        if not rep.exists():
            _write_synth(rep, spec.spots, spec.time_points, seed + k + 1)
        paths.append(rep)
    return paths


# --------------------------------------------------------------------------
# worker mode (one benchmark, one run, one JSON line)
# --------------------------------------------------------------------------


def _peak_rss_bytes() -> int:
    """Peak memory of THIS process in bytes.

    Windows: Psapi GetProcessMemoryInfo -> PeakWorkingSetSize via ctypes —
    implementation copied from tools/bench.py (which must not be imported;
    D15 directory discipline).  Linux: getrusage ru_maxrss is KiB -> *1024.
    macOS/darwin: ru_maxrss is already bytes.
    """
    import ctypes

    if sys.platform == "win32":
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_uint32),
                ("PageFaultCount", ctypes.c_uint32),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        psapi = ctypes.WinDLL("Psapi.dll")
        kernel32 = ctypes.WinDLL("kernel32.dll")
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
            ctypes.c_uint32,
        ]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        handle = kernel32.GetCurrentProcess()
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            raise OSError("GetProcessMemoryInfo failed")
        return int(counters.PeakWorkingSetSize)
    if sys.platform.startswith("linux"):
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    if sys.platform == "darwin":
        import resource

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    raise OSError(f"peak RSS unsupported on platform {sys.platform!r}")


def _run_worker(spec: BenchSpec, inputs: list[str]) -> dict:
    from pystemtc.engine import STEM

    engine = STEM(
        normalize="normalize",
        max_unit_change=2,
        max_model_profiles=spec.max_model_profiles,
        max_correlation=1.0,
        candidate_cap=1_000_000,
        n_permutations=spec.n_permutations,
        permute_t0=True,
        alpha=0.05,
        correction="bonferroni",
        cluster_min_correlation=0.7,
        cluster_corr_percentile=0.0,
        max_missing=0,
        min_abs_expr=0.5,
        change_rule="max_minus_min",
        repeat_min_correlation=0.0,
        repeat_mode="different_periods",
        spot_included=True,
    )
    t0 = time.perf_counter()
    if spec.repeat_files:
        main, *reps = inputs
        result = engine.fit(main, replicates=reps)
    else:
        result = engine.fit(inputs[0])
    wall = time.perf_counter() - t0
    payload = {
        "bench": spec.bench_id,
        "spots": spec.spots,
        "time_points": spec.time_points,
        "repeat_files": spec.repeat_files,
        "genes": len(result.gene_assignments),
        "profiles": len(result.profiles),
        "n_perms": spec.n_permutations,
        "permutation_mode": result.metadata["permutation_mode"],
        "wall_s": wall,
        "peak_rss_bytes": _peak_rss_bytes(),
        "stages": {key: result.timing[key] for key in STAGE_KEYS},
    }
    print(json.dumps(payload), flush=True)


# --------------------------------------------------------------------------
# parent mode (orchestration + aggregation)
# --------------------------------------------------------------------------


def _spawn_worker(spec: BenchSpec, inputs: list[Path]) -> dict:
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--bench-id",
        spec.bench_id,
        "--input",
        ",".join(str(p) for p in inputs),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"worker for {spec.bench_id} failed (rc={proc.returncode}):\n{proc.stderr[-2000:]}"
        )
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"worker for {spec.bench_id} produced no JSON line")
    return json.loads(lines[-1])


def _versions() -> dict[str, str]:
    import importlib.metadata

    return {
        "python": _platform.python_version(),
        "numpy": importlib.metadata.version("numpy"),
        "pandas": importlib.metadata.version("pandas"),
        "platform": _platform.platform(),
    }


CSV_FIELDS = (
    ["bench", "run", "kind", "spots", "time_points", "repeat_files",
     "genes", "profiles", "n_perms", "permutation_mode", "wall_s",
     "peak_rss_mib"]
    + [f"stage_{key}_s" for key in STAGE_KEYS]
    + ["python", "numpy", "pandas", "platform"]
)


def _csv_row(result: dict, run_idx: int, kind: str, versions: dict[str, str]) -> dict:
    row = {
        "bench": result["bench"],
        "run": run_idx,
        "kind": kind,
        "spots": result["spots"],
        "time_points": result["time_points"],
        "repeat_files": result["repeat_files"],
        "genes": result["genes"],
        "profiles": result["profiles"],
        "n_perms": result["n_perms"],
        "permutation_mode": result["permutation_mode"],
        "wall_s": round(result["wall_s"], 3),
        "peak_rss_mib": round(result["peak_rss_bytes"] / 2**20, 1),
        "python": versions["python"],
        "numpy": versions["numpy"],
        "pandas": versions["pandas"],
        "platform": versions["platform"],
    }
    for key in STAGE_KEYS:
        row[f"stage_{key}_s"] = round(result["stages"][key], 4)
    return row


def _median(values: list[float]) -> float:
    return statistics.median(values)


def _write_markdown(
    path: Path,
    specs: list[BenchSpec],
    formal_by_bench: dict[str, list[dict]],
    versions: dict[str, str],
    args: argparse.Namespace,
    stamp: str,
) -> None:
    lines = [
        "# pySTEMTC core benchmark results",
        "",
        f"- Generated (UTC): {stamp}",
        f"- Platform: {versions['platform']}",
        f"- Python {versions['python']} | numpy {versions['numpy']} | pandas {versions['pandas']}",
        f"- Seed: {args.seed} | warm-up runs: {args.warmup} | formal runs: {args.formal}"
        f" (aggregation = median, min/max kept, never averaged)",
        "- Wall time = one STEM.fit() over the whole pipeline; peak RSS = full"
        " process peak of the isolated worker (numpy/pandas import included).",
        "- Discipline (HANDOFF D15): golden proves correctness, benchmarks"
        " prove speed; any optimization is golden -> optimize -> golden.",
        "",
        "## Wall time and memory (medians over formal runs)",
        "",
        "| bench | spots | T | repeat files | genes | profiles | n_perms |"
        " permutation_mode | wall median s | wall min s | wall max s |"
        " peak RSS MiB median |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for spec in specs:
        runs = formal_by_bench[spec.bench_id]
        walls = [r["wall_s"] for r in runs]
        rss = _median([r["peak_rss_bytes"] for r in runs]) / 2**20
        first = runs[0]
        lines.append(
            f"| {spec.bench_id} | {spec.spots} | {spec.time_points} |"
            f" {spec.repeat_files} | {first['genes']} | {first['profiles']} |"
            f" {first['n_perms']} | {first['permutation_mode']} |"
            f" {_median(walls):.2f} | {min(walls):.2f} | {max(walls):.2f} | {rss:.1f} |"
        )
    lines += [
        "",
        "## Stage wall times (medians over formal runs, seconds)",
        "",
        "| bench | " + " | ".join(STAGE_KEYS) + " |",
        "|---" * (len(STAGE_KEYS) + 1) + "|",
    ]
    for spec in specs:
        runs = formal_by_bench[spec.bench_id]
        medians = [
            _median([r["stages"][key] for r in runs]) for key in STAGE_KEYS
        ]
        lines.append(
            f"| {spec.bench_id} | " + " | ".join(f"{m:.3f}" for m in medians) + " |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--bench", default=None, help="comma list of bench ids (subset)")
    ap.add_argument("--sweep", action="store_true", help="add the S* permutation-count sweep group")
    ap.add_argument("--reps", action="store_true", help="add the B7/B8 repeat-file group")
    ap.add_argument("--all", action="store_true", help="run every group")
    ap.add_argument("--warmup", type=int, default=1, help="discarded warm-up runs (default 1)")
    ap.add_argument("--formal", type=int, default=3, help="formal runs (default 3)")
    ap.add_argument("--seed", type=int, default=SEED_DEFAULT)
    ap.add_argument("--outdir", default=None, help="default: benchmarks/results/<UTCts>")
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    ap.add_argument("--bench-id", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--input", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()

    if args.worker:
        spec = ALL_SPECS[args.bench_id]
        inputs = args.input.split(",")
        _run_worker(spec, inputs)
        return

    if args.bench:
        unknown = [b for b in args.bench.split(",") if b not in ALL_SPECS]
        if unknown:
            raise SystemExit(f"unknown bench id(s): {', '.join(unknown)}")
        selected = [ALL_SPECS[b] for b in args.bench.split(",")]
    else:
        pool = list(CORE)
        if args.sweep or args.all:
            pool += SWEEP
        if args.reps or args.all:
            pool += REPEATS
        selected = pool
    if args.formal < 1:
        raise SystemExit("--formal must be >= 1")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    outdir = Path(args.outdir) if args.outdir else RESULTS / stamp
    outdir.mkdir(parents=True, exist_ok=True)
    versions = _versions()

    print(f"pySTEMTC benchmark run {stamp}: benches={[s.bench_id for s in selected]}")
    print(f"environment: {versions}", flush=True)

    csv_path = outdir / f"{stamp}_core.csv"
    md_path = outdir / f"{stamp}_core.md"
    rows: list[dict] = []
    formal_by_bench: dict[str, list[dict]] = {}

    for spec in selected:
        inputs = _ensure_inputs(spec, args.seed)
        results: list[dict] = []
        total_runs = args.warmup + args.formal
        for run_idx in range(total_runs):
            kind = "warmup" if run_idx < args.warmup else "formal"
            t0 = time.perf_counter()
            result = _spawn_worker(spec, inputs)
            rows.append(_csv_row(result, run_idx + 1, kind, versions))
            if kind == "formal":
                results.append(result)
            print(
                f"[{spec.bench_id}] {kind} run {run_idx + 1}/{total_runs}:"
                f" wall={result['wall_s']:.2f}s"
                f" rss={result['peak_rss_bytes'] / 2**20:.1f}MiB"
                f" (spawn+parse {time.perf_counter() - t0:.1f}s)",
                flush=True,
            )
        formal_by_bench[spec.bench_id] = results

    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    _write_markdown(md_path, selected, formal_by_bench, versions, args, stamp)
    print(f"CSV:  {csv_path}")
    print(f"MD:   {md_path}", flush=True)


if __name__ == "__main__":
    main()
